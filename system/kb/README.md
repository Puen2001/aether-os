# Knowledge base (LanceDB)

Local semantic + keyword search over two corpora:

- **doctrine** — the shared-knowledge vault's filed folders
  (`vaults/vault1/{concepts,entities,analysis,sources}`) — "what we know".
- **episodic** — voice digests (`system/voice/digest/`) + every vault's
  `wiki/log.md` — "what we discussed". A separate table, so the doctrine
  corpus stays pure: episodic content is weaker-signal, higher-churn, and not
  IP-clean-attested.

## What it is

- **Engine**: [LanceDB](https://lancedb.com) — embedded vector DB, no server, no daemon.
- **Embeddings**: `all-MiniLM-L6-v2` via `sentence-transformers`, run **locally**.
- **Search**: hybrid (vector nearest-neighbour + full-text BM25).
- **Index location**: `system/kb/lance/` — a derived artifact, fully rebuildable.
  Keep it git-ignored (add `system/kb/lance/` to your `.gitignore`).

## Privacy — the one leak path, closed

A knowledge base is only as private as its embedding model. Cloud embedding
APIs would ship every page to a third party on every build and every query.
This KB uses a **local** sentence-transformers model: nothing leaves the
machine — no network call at build or query time after the model is first
downloaded from HuggingFace.

## Setup (once)

```bash
cd system/kb
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
```

The keyword leg of `recall.py` also needs [ripgrep](https://github.com/BurntSushi/ripgrep)
(`rg`) on your PATH; without it, recall degrades gracefully but loses lexical
corroboration.

## Build / rebuild the index

```bash
python3 build_kb.py
```

Idempotent — overwrites both tables each run. **Cadence:** re-run after adding
or editing filed pages or after a batch of voice sessions; the index only
knows what was on disk at the last build. (A future Stop-hook step could
rebuild automatically.)

Environment overrides: `PAI_ROOT` (repo root, defaults to two levels above
this directory), `PAI_KB_VAULT` (shared-knowledge vault name, default `vault1`).

## Query

```bash
python3 query_kb.py "how does the memory sweep decide what to flag"
python3 query_kb.py -k 8 --table episodic "local embedding privacy"
```

Returns the top-k chunks with `source_path · heading` so you can open the page.

## recall() — cited retrieval (doctrine + episodic + memory)

`recall.py` sits **alongside** `query_kb.py`. Where `query_kb` searches one
table, `recall()` fuses two independent rank lists and brings the **memory
store** (`system/memory/entries/`) into the answer:

```
query
  ├─ vector leg   → LanceDB doctrine + episodic tables (semantic)
  └─ keyword leg  → ripgrep over memory entries + filed folders + digests/logs (lexical)
        │
        └─ RRF fuse (over rank lists, store-agnostic) → top-k, each tagged
                                                        [source · heading · updated · legs]
```

Two hard rules are baked into the output:

- **verify-before-rely** — results are *pointers*, not quotes to trust blindly
  (the header says so).
- **no-source-no-claim** — nothing is emitted without its source path + date.

```bash
python3 recall.py "how does the memory sweep decide what to flag"
python3 recall.py -k 8 "reply style"
python3 recall.py --scope episodic "what did we discuss last week"
```

`--scope` narrows the search: `doctrine` (filed pages + memory), `episodic`
(digests + logs), or `all` (default, fuses both). The `legs:` tag shows which
leg(s) found each hit — `V` (vector/semantic), `K` (keyword/lexical), or `VK`
(both). If the vector leg fails (index missing, embeddings error) the tool
**degrades to keyword-only** and says so in the header rather than crashing.
When the keyword leg runs but finds no lexical anchor, results are flagged
`[weak]` — semantic-only nearest-neighbours with nothing grounding them.
Pure read — `recall()` never writes the index or the vaults.

## Non-English content — the embedding caveat

The embedder (`all-MiniLM-L6-v2`) is **English-leaning**: semantic recall over
non-English text — especially non-Latin scripts — is weak. Non-English recall
rides the **keyword leg**, which is script-safe: query terms are `re.escape`'d,
never stripped with a `[^\w\s]` filter (that destroys non-Latin characters),
and ripgrep matches substrings without a word-tokenizer. So a non-English
query still finds non-English content — via `K`, not `V`. If most of your
vault is non-English, consider swapping `EMBED_MODEL` for a multilingual
sentence-transformers model (e.g. `paraphrase-multilingual-MiniLM-L12-v2`)
and rebuilding.

## v1 is deliberately thin

Plain RRF only. Deferred-until-triggered:

- **Vector-index the memory store** — trigger: ~100 memory entries OR a real
  recall miss. (Until then memory rides the keyword leg only, so it can't win
  on semantic relevance — a known v1 limitation.)
- **Recency / decay weighting** — trigger: a measured precision drop, added
  *with* an eval.
- Cross-encoder rerank; auto-rebuild hook.

## How chunking works

Each markdown file is split by `##` (H2) heading into chunks; the title and
heading are prepended to each chunk before embedding so the vector carries
document context. Frontmatter is stripped (only `title:` is read). Voice
digests (`## HH:MM:SS` turn-pairs) and vault logs (`## [date]` entries)
already split cleanly on the same boundary.

## Files

| File | Role |
|---|---|
| `build_kb.py` | Walk doctrine + episodic corpora → chunk → embed locally → write `doctrine` + `episodic` LanceDB tables + FTS indexes |
| `query_kb.py` | Embed query → hybrid search one table (`--table doctrine\|episodic`) → print ranked chunks |
| `recall.py` | Fused cited retrieval (vector + ripgrep) over doctrine + episodic + memory; `--scope` to narrow |
| `requirements.txt` | Python deps for this pack (venv-install) |
| `lance/` | The index (git-ignored, derived) |
