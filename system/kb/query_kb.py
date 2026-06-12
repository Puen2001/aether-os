#!/usr/bin/env python3
"""Query the knowledge base (LanceDB hybrid search).

Embeds the query with the same LOCAL model used at build time, runs hybrid
search (vector + full-text), and prints the top-k chunks with their source
path so you can jump straight to the filed page.

Usage:
    python3 query_kb.py "how does the memory sweep decide what to flag"
    python3 query_kb.py -k 8 "local embedding privacy"
"""
from __future__ import annotations

import argparse
import os
import sys
import textwrap
from pathlib import Path

import lancedb
from lancedb.embeddings import get_registry

# Repo root resolves from this script's own location (system/kb/ → root);
# override with the PAI_ROOT env var if the tree lives elsewhere.
ROOT = Path(os.environ.get("PAI_ROOT") or Path(__file__).resolve().parents[2])
DB_DIR = ROOT / "system" / "kb" / "lance"
TABLE = "doctrine"
EMBED_MODEL = "all-MiniLM-L6-v2"


def main() -> None:
    ap = argparse.ArgumentParser(description="Query the knowledge base.")
    ap.add_argument("query", nargs="+", help="natural-language question")
    ap.add_argument("-k", type=int, default=5, help="number of results (default 5)")
    ap.add_argument("--table", choices=["doctrine", "episodic"], default="doctrine",
                    help="which table to search (default doctrine). For fused "
                         "doctrine+episodic+memory recall use recall.py instead.")
    args = ap.parse_args()
    query = " ".join(args.query)

    if not DB_DIR.exists():
        sys.exit("knowledge base not built yet — run build_kb.py first.")

    # Register the embedding fn so the table knows how to embed the query.
    get_registry().get("sentence-transformers").create(name=EMBED_MODEL, device="cpu")

    db = lancedb.connect(DB_DIR)
    if args.table not in db.table_names():
        sys.exit(f"table {args.table!r} not built yet — run build_kb.py first.")
    table = db.open_table(args.table)

    results = table.search(query, query_type="hybrid").limit(args.k).to_list()

    if not results:
        print("no matches.")
        return

    print(f'\n"{query}"  ->  top {len(results)} of {table.count_rows()} chunks\n')
    for i, r in enumerate(results, 1):
        score = r.get("_relevance_score", r.get("_distance", 0))
        print(f"[{i}] {r['source_path']}  ·  {r['heading']}   (score {score:.3f})")
        snippet = r["text"].split("\n\n", 1)[-1].strip().replace("\n", " ")
        print(textwrap.fill(snippet[:280] + ("…" if len(snippet) > 280 else ""),
                            width=88, initial_indent="    ", subsequent_indent="    "))
        print()


if __name__ == "__main__":
    main()
