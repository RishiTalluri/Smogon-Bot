"""
scripts/migrate_pkl_to_jsonl.py
──────────────────────────────────
One-time migration for anyone who already has RAG_Data/docs.pkl + a matching
faiss_index.bin from the old pipeline. Re-embedding the whole corpus isn't
necessary — the FAISS vectors are still valid for the same text. This script:

  1. Loads the old pickled list of plain-text chunks (row i == FAISS row i)
  2. Best-effort re-parses "Title:/Forum:/URL:" out of each chunk's embedded
     header (present for chunks that were the FIRST chunk of their source doc
     — later chunks from the old pipeline never had a header at all, which
     was the original bug; those get title="unknown" and still work fine for
     vector search, just without graph edges to a specific thread title)
  3. Extracts entity tags (mons/tiers) from the chunk text for the graph
  4. Writes chunks.jsonl (row order preserved — required for FAISS id lookup)
  5. Builds and saves graph.json

The old docs.pkl is left untouched on disk; nothing here deletes it.

Run from anywhere:
    python scripts/migrate_pkl_to_jsonl.py
"""

import os
import pickle
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rag_engine import config
from rag_engine.entities import extract_entities
from rag_engine.storage import ChunkStore, save_chunks
from rag_engine.graph_store import build_graph, save_graph, graph_stats

HEADER_RE = re.compile(
    r"Title:\s*(?P<title>.*?)\s*\n"
    r"Forum:\s*(?P<forum>.*?)\s*\n"
    r"URL:\s*(?P<url>.*?)\s*\n",
    re.IGNORECASE,
)


def parse_legacy_chunk(text: str) -> dict:
    is_team = text.strip().startswith("[POKEMON TEAM]")
    m = HEADER_RE.search(text)
    title = m.group("title") if m else "unknown"
    forum = m.group("forum") if m else "unknown"
    url   = m.group("url") if m else "unknown"
    return {"title": title, "forum": forum, "url": url, "is_team": is_team}


def main():
    if not os.path.exists(config.LEGACY_CHUNKS_PKL_PATH):
        print(f"[ERROR] No legacy pickle found at {config.LEGACY_CHUNKS_PKL_PATH}")
        print("If you don't have an existing docs.pkl, use scripts/build_index.py instead.")
        sys.exit(1)

    if not os.path.exists(config.FAISS_INDEX_PATH):
        print(f"[ERROR] No FAISS index found at {config.FAISS_INDEX_PATH} — migration requires")
        print("the existing index since row order must match docs.pkl exactly.")
        sys.exit(1)

    print(f"Loading legacy chunks from {config.LEGACY_CHUNKS_PKL_PATH} ...")
    with open(config.LEGACY_CHUNKS_PKL_PATH, "rb") as f:
        legacy_chunks = pickle.load(f)
    print(f"Loaded {len(legacy_chunks)} legacy chunks")

    records = []
    header_found = 0
    for i, raw in enumerate(legacy_chunks):
        text = str(raw)
        meta = parse_legacy_chunk(text)
        if meta["title"] != "unknown":
            header_found += 1
        entities = extract_entities(text)
        records.append({
            "id": i,   # MUST match FAISS row order — do not resort
            "text": text,
            "content": text,
            "title": meta["title"],
            "forum": meta["forum"],
            "url": meta["url"],
            "is_team": meta["is_team"],
            "mons": entities["mons"],
            "tiers": entities["tiers"],
            "gen_tag": entities["gen_tag"],
            "source": "migrated",
        })

    print(f"Recovered title/forum/url header on {header_found}/{len(records)} chunks "
          f"({header_found / max(len(records),1):.0%}) — the rest keep title='unknown' "
          f"(this was the pre-existing metadata-loss bug in the old chunker, now fixed "
          f"going forward in scripts/build_index.py).")

    save_chunks(records, config.CHUNKS_PATH)
    print(f"Wrote {config.CHUNKS_PATH}")

    print("Building entity co-occurrence graph...")
    chunk_store = ChunkStore(records)
    graph = build_graph(chunk_store)
    save_graph(graph)
    stats = graph_stats(graph)

    print("\n✅ Migration complete")
    print(f"  - {config.CHUNKS_PATH} (new — replaces docs.pkl)")
    print(f"  - {config.GRAPH_PATH} (new)")
    print(f"  - {config.FAISS_INDEX_PATH} (untouched, reused as-is)")
    print(
        f"\nGraph: {stats['chunk_nodes']} chunk nodes, {stats['mon_nodes']} mon nodes, "
        f"{stats['tier_nodes']} tier nodes, {stats['edges']} edges"
    )
    print(f"\ndocs.pkl was left in place at {config.LEGACY_CHUNKS_PKL_PATH} — safe to delete once "
          f"you've confirmed the new files work.")


if __name__ == "__main__":
    main()
