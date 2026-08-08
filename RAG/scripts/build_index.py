"""
scripts/build_index.py
─────────────────────────
Replaces DataCleaning/Rag_index_builder.py. Reads the raw scraped Smogon data,
chunks it, embeds it, and writes three artifacts to RAG_Data/:

  - faiss_index.bin   (unchanged format — FAISS's own binary index)
  - chunks.jsonl        (replaces docs.pkl — structured, one JSON record per line)
  - graph.json           (NEW — entity co-occurrence graph for GraphRAG)

Fix vs. the old script: previously the Title/Forum/URL metadata header was
prepended to the *document* once, then chunk_text() split by word count —
so only the first ~300-word chunk of any long thread kept its metadata; every
later chunk from the same thread lost title/forum/url entirely. Here, chunking
happens on raw content only, and metadata is attached to every resulting
sub-chunk independently.

Run from anywhere:
    python scripts/build_index.py
    python scripts/build_index.py --limit 500   # test on a subset first — see below
"""

import argparse
import json
import os
import sys
import time

import numpy as np
import pandas as pd
import faiss
from tqdm import tqdm
from sentence_transformers import SentenceTransformer

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # so `rag_engine` imports work

from rag_engine import config
from rag_engine.entities import extract_entities
from rag_engine.chunking import chunk_document
from rag_engine.storage import ChunkStore, save_chunks
from rag_engine.graph_store import build_graph, save_graph, graph_stats


def fmt_duration(seconds: float) -> str:
    seconds = int(seconds)
    if seconds < 60:
        return f"{seconds}s"
    m, s = divmod(seconds, 60)
    if m < 60:
        return f"{m}m {s}s"
    h, m = divmod(m, 60)
    return f"{h}h {m}m {s}s"


class Phase:
    """Context manager that prints a start banner and a 'done in Xs' line,
    and records duration in the shared `phase_times` dict for the final
    summary — so every step of a long run is visibly moving, not just
    embedding."""

    def __init__(self, name: str, phase_times: dict):
        self.name = name
        self.phase_times = phase_times

    def __enter__(self):
        print(f"\n[*] {self.name} ...")
        self.start = time.time()
        return self

    def __exit__(self, *exc):
        elapsed = time.time() - self.start
        self.phase_times[self.name] = elapsed
        print(f"[✓] {self.name} — done in {fmt_duration(elapsed)}")

# ─── INPUT FILES ─────────────────────────────────────────────────────────────────
CRAWLER_DATA_DIR = os.path.join(config.RAG_DIR, "..", "Crawler", "dataObtained")
FILES = [
    os.path.join(CRAWLER_DATA_DIR, "smogon_threads.csv"),
    os.path.join(CRAWLER_DATA_DIR, "smogon_threads.json"),
    os.path.join(CRAWLER_DATA_DIR, "smogon_full_text.txt"),
]


def clean_text(text) -> str:
    return "" if text is None else str(text).strip()


# ─── LOAD RAW DOCS (metadata kept separate from content, not baked in yet) ───────

def process_csv(path: str) -> list[dict]:
    print(f"Processing CSV: {path}")
    df = pd.read_csv(path)
    docs = []
    # itertuples() instead of iterrows() — iterrows() rebuilds a Series per
    # row and is noticeably slower at tens of thousands of rows.
    for row in tqdm(df.itertuples(index=False), total=len(df), desc="Reading CSV rows", unit="row"):
        row = row._asdict()
        content = clean_text(row.get("op_text"))
        if not content:
            continue
        docs.append({
            "content": content,
            "title": clean_text(row.get("title")) or "unknown",
            "forum": clean_text(row.get("forum")) or "unknown",
            "url": clean_text(row.get("url")) or "unknown",
            "source": "csv",
        })
    return docs


def process_json(path: str) -> list[dict]:
    print(f"Processing JSON: {path}")
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    docs = []
    for item in tqdm(data, desc="Reading JSON items", unit="item"):
        content = clean_text(item.get("op_text"))
        if not content:
            continue
        docs.append({
            "content": content,
            "title": clean_text(item.get("title")) or "unknown",
            "forum": clean_text(item.get("forum")) or "unknown",
            "url": clean_text(item.get("url")) or "unknown",
            "source": "json",
        })
    return docs


def process_txt(path: str) -> list[dict]:
    print(f"Processing TXT: {path}")
    with open(path, "r", encoding="utf-8") as f:
        text = f.read()
    docs = []
    for part in text.split("\n\n"):
        part = clean_text(part)
        if not part:
            continue
        docs.append({
            "content": part,
            "title": "unknown",
            "forum": "unknown",
            "url": "unknown",
            "source": f"txt:{os.path.basename(path)}",
        })
    return docs


# Chunking now lives in rag_engine/chunking.py — post-boundary aware,
# sentence-aware, and pokepaste-aware. See that module's docstring for why
# the old chunk_words()/is_team() here were replaced.


def build_records(docs: list[dict]) -> list[dict]:
    """
    Chunk each doc's content with chunk_document() (post-boundary aware,
    sentence-aware, pokepaste-aware — see rag_engine/chunking.py), then
    attach that doc's metadata to EVERY resulting sub-chunk. is_team is now
    decided per sub-chunk, not per whole document, since a single thread
    can contain both team-export posts and pure discussion posts.
    """
    records = []
    next_id = 0

    pbar = tqdm(docs, desc="Chunking documents", unit="doc")
    for doc in pbar:
        sub_chunks = chunk_document(doc["content"])

        for sub in sub_chunks:
            tag = "[POKEMON TEAM]" if sub["is_team"] else "[DISCUSSION]"
            header = f"Title: {doc['title']}\nForum: {doc['forum']}\nURL: {doc['url']}"
            full_text = f"{tag}\n{header}\n\n{sub['text']}"

            entities = extract_entities(full_text)

            records.append({
                "id": next_id,
                "text": full_text,        # what gets embedded + sent to the LLM as context
                "content": sub["text"],    # raw content only, for debug snippets
                "title": doc["title"],
                "forum": doc["forum"],
                "url": doc["url"],
                "is_team": sub["is_team"],
                "mons": entities["mons"],
                "tiers": entities["tiers"],
                "gen_tag": entities["gen_tag"],
                "source": doc["source"],
            })
            next_id += 1
        pbar.set_postfix(chunks=next_id)

    return records


def parse_args():
    p = argparse.ArgumentParser(description="Build FAISS index + chunk store + entity graph")
    p.add_argument(
        "--limit", type=int, default=None,
        help="Only process the first N documents — use this to test the pipeline "
             "and eyeball chunk quality before running the full corpus (which can "
             "take a long time to embed on CPU for a large scrape).",
    )
    p.add_argument(
        "--test-run", action="store_true",
        help="Write output to RAG_Data/test_run/ instead of RAG_Data/ directly, so "
             "a trial run never overwrites a real index. Implied automatically when "
             "--limit is used.",
    )
    return p.parse_args()


def main():
    args = parse_args()
    test_mode = args.test_run or args.limit is not None
    run_start = time.time()
    phase_times: dict[str, float] = {}

    if test_mode:
        out_dir = os.path.join(config.DATA_DIR, "test_run")
        os.makedirs(out_dir, exist_ok=True)
        config.FAISS_INDEX_PATH = os.path.join(out_dir, "faiss_index.bin")
        config.CHUNKS_PATH = os.path.join(out_dir, "chunks.jsonl")
        config.GRAPH_PATH = os.path.join(out_dir, "graph.json")
        print(f"[TEST RUN] Writing to {out_dir} — the real RAG_Data/ files will not be touched.\n")

    with Phase("Loading raw documents", phase_times):
        all_docs = []
        any_found = False
        for path in FILES:
            if not os.path.exists(path):
                print(f"[skip] Not found: {path}")
                continue
            any_found = True
            if path.endswith(".csv"):
                all_docs.extend(process_csv(path))
            elif path.endswith(".json"):
                all_docs.extend(process_json(path))
            elif path.endswith(".txt"):
                all_docs.extend(process_txt(path))

        if not any_found:
            print(f"\n[ERROR] None of the expected input files were found under {CRAWLER_DATA_DIR}")
            print("Expected (any subset is fine):")
            for f in FILES:
                print(f"  - {f}")
            sys.exit(1)

        print(f"Total documents found: {len(all_docs)}")
        if args.limit is not None:
            all_docs = all_docs[:args.limit]
            print(f"--limit {args.limit} applied → processing {len(all_docs)} documents")

    with Phase("Chunking documents", phase_times):
        records = build_records(all_docs)
        tagged = sum(1 for r in records if r["mons"] or r["tiers"])
        team_chunks = sum(1 for r in records if r["is_team"])
        print(f"Total chunks: {len(records)}")
        print(f"Chunks with at least one entity tag: {tagged} ({tagged / max(len(records),1):.0%})")
        print(f"Team-export chunks: {team_chunks}")

    with Phase(f"Loading embedding model ({config.EMBED_MODEL})", phase_times):
        model = SentenceTransformer(config.EMBED_MODEL)
        try:
            device = str(model.device)
        except Exception:
            device = "unknown"
        print(f"Device: {device}" + ("  (CPU — this will be the slowest phase; a GPU would help a lot)"
                                       if device.startswith("cpu") else ""))

    with Phase(f"Embedding {len(records)} chunks", phase_times):
        texts = [r["text"] for r in records]
        embeddings = model.encode(texts, show_progress_bar=True, batch_size=64)

    with Phase("Building FAISS index", phase_times):
        dim = embeddings.shape[1]
        index = faiss.IndexFlatL2(dim)
        index.add(np.array(embeddings).astype("float32"))
        os.makedirs(os.path.dirname(config.FAISS_INDEX_PATH), exist_ok=True)
        faiss.write_index(index, config.FAISS_INDEX_PATH)
        save_chunks(records, config.CHUNKS_PATH)

    with Phase("Building entity co-occurrence graph", phase_times):
        chunk_store = ChunkStore(records)
        graph = build_graph(chunk_store)
        save_graph(graph)
        stats = graph_stats(graph)

    total_elapsed = time.time() - run_start

    print("\n✅ DONE")
    print("Saved:")
    print(f"  - {config.FAISS_INDEX_PATH}")
    print(f"  - {config.CHUNKS_PATH}")
    print(f"  - {config.GRAPH_PATH}")
    print(
        f"\nGraph: {stats['chunk_nodes']} chunk nodes, {stats['mon_nodes']} mon nodes, "
        f"{stats['tier_nodes']} tier nodes, {stats['edges']} edges"
    )

    print(f"\nTime breakdown:")
    for name, elapsed in phase_times.items():
        pct = (elapsed / total_elapsed * 100) if total_elapsed > 0 else 0
        print(f"  {name:<40} {fmt_duration(elapsed):>10}  ({pct:4.1f}%)")
    print(f"  {'TOTAL':<40} {fmt_duration(total_elapsed):>10}")


if __name__ == "__main__":
    main()
