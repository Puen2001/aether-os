#!/usr/bin/env python3
"""Build the local knowledge base (LanceDB + local embeddings).

Walks the shared-knowledge vault's filed folders, chunks each markdown file by
H2 heading, embeds every chunk with a LOCAL sentence-transformers model (no
network, no third-party API — see the privacy note in README.md), and writes
them into LanceDB tables with both a vector index and a full-text index so
queries can run hybrid (semantic + keyword) search.

Idempotent: re-running overwrites the tables from scratch.

Usage:
    python3 build_kb.py
"""
from __future__ import annotations

import os
import re
from pathlib import Path

# The embedding model downloads once from its host on first build; suppress the
# Hugging Face hub telemetry ping while fetching it (your vault data never leaves
# — only the model is downloaded). Mirrors recall.py.
os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")

import lancedb
from lancedb.embeddings import get_registry
from lancedb.pydantic import LanceModel, Vector

# ── Layout ────────────────────────────────────────────────────────────────
# Repo root resolves from this script's own location (system/kb/ → root);
# override with the PAI_ROOT env var if the tree lives elsewhere.
ROOT = Path(os.environ.get("PAI_ROOT") or Path(__file__).resolve().parents[2])
DB_DIR = ROOT / "system" / "kb" / "lance"   # derived artifact — keep git-ignored
TABLE = "doctrine"

# Shared-knowledge vault (the filed zone; pages carry ip_clean: true).
# Override with PAI_KB_VAULT if you designated a different vault.
VAULT = ROOT / "vaults" / os.environ.get("PAI_KB_VAULT", "vault1")

# Filed folders to index for the doctrine table ("what we know").
SOURCES = ["concepts", "entities", "analysis", "sources"]

EPISODIC_TABLE = "episodic"
# Episodic / conversational corpus — "what we discussed", not "what we know".
# Reuses the same H2 chunker: voice digests are `## HH:MM:SS` turn-pairs and
# vault logs are `## [date]` entries — both already split cleanly per H2. Kept
# in a SEPARATE table so the doctrine table stays pure (episodic is
# weaker-signal, higher-churn, and not ip_clean-attested).
EPISODIC_SOURCES = [
    ROOT / "system" / "voice" / "digest",               # voice-session digests (dir, *.md)
    *sorted((ROOT / "vaults").glob("*/wiki/log.md")),   # per-vault logs (single files)
]

# Local embedding model — small, fast, fully offline. 384-dim.
# NOTE: English-leaning. Non-English content (especially non-Latin scripts)
# embeds weakly, so semantic recall over it is poor; recall.py's ripgrep
# keyword leg is the script-safe fallback. See README.
EMBED_MODEL = "all-MiniLM-L6-v2"

FRONTMATTER = re.compile(r"^---\n.*?\n---\n", re.DOTALL)
H2 = re.compile(r"^##\s+", re.MULTILINE)


def strip_frontmatter(text: str) -> tuple[str, dict]:
    """Return (body, frontmatter-dict). Only title is parsed; rest ignored."""
    meta: dict[str, str] = {}
    m = FRONTMATTER.match(text)
    if m:
        block = m.group(0)
        for line in block.splitlines():
            if line.startswith("title:"):
                meta["title"] = line.split(":", 1)[1].strip()
        text = text[m.end():]
    return text, meta


def chunk(body: str) -> list[tuple[str, str]]:
    """Split a markdown body into (heading, text) chunks by H2 boundary."""
    parts = H2.split(body)
    chunks: list[tuple[str, str]] = []
    # parts[0] is the pre-first-H2 intro (may include the H1 title block)
    intro = parts[0].strip()
    if intro:
        chunks.append(("(intro)", intro))
    # Each remaining part is the body of an H2 section; restore the marker.
    for section in parts[1:]:
        lines = section.splitlines()
        heading = lines[0].strip() if lines else ""
        chunks.append((heading, "## " + section.strip()))
    return chunks


def _records_from(md: Path, base: Path) -> list[dict]:
    """Chunk one markdown file → records. `source_path` is stored relative to
    `base` (VAULT for doctrine, ROOT for episodic so digest paths resolve)."""
    raw = md.read_text(encoding="utf-8", errors="replace")
    body, meta = strip_frontmatter(raw)
    title = meta.get("title", md.stem)
    rel = str(md.relative_to(base))
    out: list[dict] = []
    for heading, text in chunk(body):
        if not text.strip():
            continue
        # Prepend title+heading so the embedding carries document context.
        if heading == "(intro)":
            embed_text = f"{title}\n\n{text}"
        else:
            embed_text = f"{title} — {heading}\n\n{text}"
        out.append({
            "text": embed_text,
            "source_path": rel,
            "title": title,
            "heading": heading,
        })
    return out


def collect() -> list[dict]:
    """Doctrine corpus — VAULT-relative source paths."""
    records: list[dict] = []
    for folder in SOURCES:
        src = VAULT / folder
        if not src.is_dir():
            continue
        for md in sorted(src.glob("*.md")):
            records.extend(_records_from(md, VAULT))
    return records


def collect_episodic() -> list[dict]:
    """Episodic corpus (voice digests + vault logs) — ROOT-relative paths."""
    files: list[Path] = []
    for src in EPISODIC_SOURCES:
        if src.is_dir():
            files += sorted(src.glob("*.md"))
        elif src.exists():
            files.append(src)
    records: list[dict] = []
    for md in files:
        records.extend(_records_from(md, ROOT))
    return records


def _build_table(db, schema, name: str, records: list[dict]) -> None:
    """Create/overwrite one table + its FTS index. Empty record set → skip."""
    if not records:
        print(f"  {name}: nothing to index — skipped.")
        return
    table = db.create_table(name, schema=schema, mode="overwrite")
    table.add(records)
    table.create_fts_index("text", replace=True)
    print(f"  {name}: indexed {len(records)} chunks")


def main() -> None:
    print(f"root: {ROOT}")
    doctrine_records = collect()
    episodic_records = collect_episodic()
    print(f"collected {len(doctrine_records)} doctrine chunks ({len(SOURCES)} folders) "
          f"+ {len(episodic_records)} episodic chunks")
    if not doctrine_records and not episodic_records:
        print("nothing to index — aborting.")
        return

    model = get_registry().get("sentence-transformers").create(
        name=EMBED_MODEL, device="cpu"
    )

    class Doc(LanceModel):
        text: str = model.SourceField()
        vector: Vector(model.ndims()) = model.VectorField()  # type: ignore[valid-type]
        source_path: str
        title: str
        heading: str

    db = lancedb.connect(DB_DIR)
    _build_table(db, Doc, TABLE, doctrine_records)
    _build_table(db, Doc, EPISODIC_TABLE, episodic_records)
    print(f"done → {DB_DIR}")
    print("query with: python3 recall.py 'your question'")


if __name__ == "__main__":
    main()
