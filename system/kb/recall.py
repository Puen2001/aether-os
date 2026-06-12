#!/usr/bin/env python3
"""recall() — unified cited retrieval over the knowledge base + memory.

A thin retrieval glue layer, NOT a new store: it fuses two independent rank
lists —

    vector leg   → the LanceDB doctrine + episodic tables (semantic)
    keyword leg  → ripgrep over memory + filed folders + episodic corpus (lexical)

— with Reciprocal Rank Fusion (store-agnostic, over RANK LISTS), and prints the
top-k with provenance. The keyword leg is what brings the memory store into
recall() for v1; memory is NOT vector-indexed until it grows past ~100 entries
(see README).

`--scope` narrows the search: "doctrine" (filed pages + memory — "what we
know") or "episodic" (voice digests + vault logs — "what we discussed");
default "all" fuses both.

Two hard rules, baked in:
  - verify-before-rely  — results are POINTERS, not quotes to trust blindly.
  - no-source-no-claim  — nothing is emitted without its source path + date.

Plain fusion only in v1 (every leg weighted equally); recency is a documented
next signal, added later WITH an eval.

Usage:
    python3 recall.py "how does the memory sweep decide what to flag"
    python3 recall.py -k 8 "embedding model choice"
    python3 recall.py --scope episodic "what did we discuss last week"
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import textwrap
import warnings
from datetime import datetime
from pathlib import Path

# CLI hygiene: the LanceDB table_names() deprecation + HF unauthenticated notice
# are cosmetic noise for a read-only query tool. Keep stdout clean.
warnings.filterwarnings("ignore", category=DeprecationWarning)
os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")
os.environ.setdefault("TRANSFORMERS_NO_ADVISORY_WARNINGS", "1")

# ── Layout ──────────────────────────────────────────────────────────────────
# Repo root resolves from this script's own location (system/kb/ → root);
# override with the PAI_ROOT env var if the tree lives elsewhere.
HERE = Path(__file__).resolve().parent
ROOT = Path(os.environ.get("PAI_ROOT") or HERE.parents[1])
DB_DIR = ROOT / "system" / "kb" / "lance"
TABLE = "doctrine"
EPISODIC_TABLE = "episodic"
EMBED_MODEL = "all-MiniLM-L6-v2"

# Shared-knowledge vault — mirror build_kb.py (override with PAI_KB_VAULT).
VAULT = ROOT / "vaults" / os.environ.get("PAI_KB_VAULT", "vault1")

# Memory store (covered by the keyword leg only in v1).
MEMORY_DIR = ROOT / "system" / "memory" / "entries"

# Filed folders — mirror build_kb.py SOURCES (the vector index covers these).
DOCTRINE_FOLDERS = ["concepts", "entities", "analysis", "sources"]

# Episodic corpus — mirror build_kb.py EPISODIC_SOURCES. ROOT-relative so the
# voice digests resolve. Searched by the keyword leg + the episodic table.
EPISODIC_PATHS = [
    ROOT / "system" / "voice" / "digest",
    *sorted((ROOT / "vaults").glob("*/wiki/log.md")),
]

RRF_K = 60          # standard RRF damping constant
DATE_RE = re.compile(r"^updated:\s*(\d{4}-\d{2}-\d{2})", re.MULTILINE)

# Optional, evidence-only alias expansion. Tiny on purpose — grow it with an
# eval, not vibes. Applied to the keyword leg to widen lexical recall.
# Replace these placeholders with aliases from YOUR domain.
ALIASES = {
    "kb": "knowledge base",
    "embeddings": "embedding",
}


# ── Provenance ────────────────────────────────────────────────────────────────
def file_date(path: Path) -> str:
    """Last-updated date as YYYY-MM-DD. Filed pages: frontmatter `updated:` if
    present; otherwise (and for memory, which has no such field) file mtime."""
    try:
        head = path.read_text(encoding="utf-8", errors="replace")[:1500]
        m = DATE_RE.search(head)
        if m:
            return m.group(1)
    except OSError:
        pass
    try:
        return datetime.fromtimestamp(path.stat().st_mtime).strftime("%Y-%m-%d")
    except OSError:
        return "unknown"


def label(path: Path) -> str:
    """Human-facing source label, vault-relative where possible. Tries VAULT
    first (→ `concepts/x.md`), then ROOT (→ `system/voice/digest/x.md` for
    episodic digests, `system/memory/entries/x.md` for memory). Anything
    outside the tree falls back to `memory/<name>`."""
    for base in (VAULT, ROOT):
        try:
            return str(path.relative_to(base))
        except ValueError:
            continue
    return "memory/" + path.name


# ── Vector leg (semantic) — reuses the built LanceDB tables ───────────────────
def vector_leg(query: str, depth: int, scope: str = "all") -> list[dict]:
    """Ranked chunks via semantic search over the in-scope table(s). Raises on
    any failure so the caller can degrade to keyword-only. `scope` selects
    doctrine, episodic, or both.

    source_path is stored relative to the table's base (VAULT for doctrine,
    ROOT for episodic), so each table reconstructs against the right base."""
    import lancedb
    from lancedb.embeddings import get_registry

    if not DB_DIR.exists():
        raise FileNotFoundError(f"index not built: {DB_DIR}")
    get_registry().get("sentence-transformers").create(name=EMBED_MODEL, device="cpu")
    db = lancedb.connect(DB_DIR)
    names = db.table_names()  # plain list; list_tables() returns a response obj

    targets: list[tuple[str, Path]] = []         # (table, source_path base)
    if scope in ("all", "doctrine") and TABLE in names:
        targets.append((TABLE, VAULT))
    if scope in ("all", "episodic") and EPISODIC_TABLE in names:
        targets.append((EPISODIC_TABLE, ROOT))
    if not targets:
        raise FileNotFoundError(f"no in-scope table for {scope!r} — run build_kb.py")

    out: list[dict] = []
    for tname, base in targets:
        rows = db.open_table(tname).search(query, query_type="vector").limit(depth).to_list()
        for r in rows:
            out.append({
                "path": (base / r["source_path"]),
                "heading": r.get("heading", ""),
                "text": r.get("text", ""),
            })
    return out


# ── Keyword leg (lexical) — ripgrep over memory + filed folders ───────────────
def keyword_leg(query: str, depth: int, scope: str = "all") -> tuple[list[dict], bool]:
    """Ranked files by literal-term match count. Terms are re.escape'd (never
    stripped with a [^\\w\\s] filter — that destroys non-Latin scripts), so
    queries in any script pass through intact.

    Returns (hits, ran). `ran` is False ONLY when ripgrep itself was
    unavailable/timed out — so the caller can tell "keyword leg found no anchor"
    (ran=True, hits=[]) apart from "keyword leg couldn't run" (ran=False). That
    distinction powers the no-keyword-corroboration guard in recall()."""
    terms = [t for t in query.split() if t]
    expanded = list(terms)
    for t in terms:
        alias = ALIASES.get(t.lower())
        if alias:
            expanded.append(alias)
    if not expanded:
        return [], True                      # ran conceptually; empty query, no anchor
    pattern = "|".join(re.escape(t) for t in expanded)

    # doctrine scope carries the memory store (the governed facts live with the
    # "what we know" layer); episodic scope carries digests + vault logs.
    search_paths: list[str] = []
    if scope in ("all", "doctrine"):
        search_paths += [str(MEMORY_DIR)] + [str(VAULT / f) for f in DOCTRINE_FOLDERS]
    if scope in ("all", "episodic"):
        search_paths += [str(p) for p in EPISODIC_PATHS]
    search_paths = [p for p in search_paths if Path(p).exists()]
    if not search_paths:
        return [], True                      # ran conceptually; nothing in scope to grep

    cmd = ["rg", "--json", "-i", "-g", "*.md", "-e", pattern, *search_paths]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return [], False                     # ripgrep missing → corroboration uncheckable

    counts: dict[str, int] = {}
    for line in proc.stdout.splitlines():
        try:
            obj = json.loads(line)
        except ValueError:
            continue
        if obj.get("type") == "match":
            p = obj["data"]["path"]["text"]
            counts[p] = counts.get(p, 0) + 1

    ranked = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[:depth]
    return [{"path": Path(p), "matches": n} for p, n in ranked], True


# ── Fusion ────────────────────────────────────────────────────────────────────
def rrf_fuse(legs: list[list[Path]]) -> dict[str, float]:
    """Reciprocal Rank Fusion over rank lists, keyed by source label. Plain
    fusion: every leg weighted 1.0 (no recency/decay in v1)."""
    scores: dict[str, float] = {}
    for ranklist in legs:
        for rank, path in enumerate(ranklist, start=1):
            key = label(path)
            scores[key] = scores.get(key, 0.0) + 1.0 / (RRF_K + rank)
    return scores


# ── Orchestration ─────────────────────────────────────────────────────────────
def recall(query: str, k: int = 5, scope: str = "all") -> dict:
    """Return {'degraded': bool, 'results': [...]}. Pure read — never writes.

    `scope`: "all" (default), "doctrine" (filed pages + memory), or "episodic"
    (voice digests + vault logs — "what we discussed")."""
    depth = max(k * 3, 15)        # over-fetch per leg, fuse, then trim to k

    degraded = False
    try:
        vhits = vector_leg(query, depth, scope)
    except Exception:
        vhits = []
        degraded = True
    khits, kw_available = keyword_leg(query, depth, scope)

    # Best vector chunk per path (first = best rank) for display.
    vbest: dict[str, dict] = {}
    vpaths: list[Path] = []
    for h in vhits:
        key = label(h["path"])
        if key not in vbest:
            vbest[key] = h
            vpaths.append(h["path"])
    kpaths = [h["path"] for h in khits]

    scores = rrf_fuse([vpaths, kpaths])
    legs_hit: dict[str, str] = {}
    for p in vpaths:
        legs_hit[label(p)] = legs_hit.get(label(p), "") + "V"
    for p in kpaths:
        legs_hit[label(p)] = legs_hit.get(label(p), "") + "K"

    # Map label → path for snippet/date lookup.
    by_label: dict[str, Path] = {label(p): p for p in vpaths + kpaths}

    ordered = sorted(scores.items(), key=lambda kv: -kv[1])[:k]
    results = []
    for key, score in ordered:
        path = by_label[key]
        chunk = vbest.get(key)
        if chunk:
            heading = chunk["heading"] or "(intro)"
            body = chunk["text"].split("\n\n", 1)[-1]
        else:                                   # keyword-only hit
            heading = "(keyword)"
            try:
                raw = path.read_text(encoding="utf-8", errors="replace")
                body = re.sub(r"^---\n.*?\n---\n", "", raw, flags=re.DOTALL)
            except OSError:
                body = ""
        snippet = body.strip().replace("\n", " ")
        results.append({
            "source": key,
            "heading": heading,
            "updated": file_date(path),
            "legs": legs_hit.get(key, ""),
            "score": score,
            "snippet": snippet,
        })
    # Corroboration guard (no tuned threshold — deterministic): when the keyword
    # leg RAN and found zero lexical anchor, the vector hits are semantic-only
    # nearest-neighbours with nothing grounding them → flag as weak so recall()
    # can honour no-source-no-claim instead of citing confident garbage.
    return {
        "degraded": degraded,
        "kw_available": kw_available,
        "corroborated": bool(khits),
        "results": results,
    }


def main() -> None:
    ap = argparse.ArgumentParser(description="recall() — cited retrieval over the KB + memory.")
    ap.add_argument("query", nargs="+", help="natural-language question")
    ap.add_argument("-k", type=int, default=5, help="number of results (default 5)")
    ap.add_argument("--scope", choices=["all", "doctrine", "episodic"], default="all",
                    help="all (default) | doctrine (filed pages+memory) | episodic (digests+logs)")
    args = ap.parse_args()
    query = " ".join(args.query)

    out = recall(query, args.k, args.scope)
    res = out["results"]
    # keyword leg ran and found no lexical anchor → results are semantic-only guesses
    weak = out["kw_available"] and not out["corroborated"]

    notes = []
    if out["degraded"]:
        notes.append("vector leg down — keyword-only")
    if not out["kw_available"]:
        notes.append("keyword leg down — ripgrep missing; corroboration unchecked")
    flag = ("  [" + "; ".join(notes) + "]") if notes else ""
    print(f'\nrecall: "{query}"  ->  top {len(res)}'
          f'   (verify before relying — pointers, not quotes){flag}\n')

    if not res:
        print("    no matches. (no source → no claim)\n")
        return

    if weak:
        print("    WARNING: NO KEYWORD CORROBORATION — the keyword leg found no lexical")
        print("      anchor for this query, so the hits below are semantic-only guesses.")
        print("      Treat as LIKELY NO MATCH; verify hard before relying. (no-source-no-claim)\n")

    for i, r in enumerate(res, 1):
        mark = "[weak] " if weak else ""
        print(f"[{i}] {mark}{r['source']}  ·  {r['heading']}  ·  updated:{r['updated']}"
              f"  ·  legs:{r['legs']}   (score {r['score']:.4f})")
        snip = r["snippet"]
        print(textwrap.fill(snip[:280] + ("…" if len(snip) > 280 else ""),
                            width=88, initial_indent="    ", subsequent_indent="    "))
        print()


if __name__ == "__main__":
    main()
