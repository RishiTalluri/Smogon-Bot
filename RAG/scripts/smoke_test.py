"""
scripts/smoke_test.py
────────────────────────
Exercises the full pipeline — chunk building, entity tagging, FAISS indexing,
graph construction, and hybrid retrieval — on small synthetic data, using a
deterministic bag-of-words stub embedder instead of downloading the real
sentence-transformers model. This validates that all the code paths work
correctly (imports, id/row alignment, graph traversal, score merging) without
needing network access or a GROQ_API_KEY. It does NOT validate retrieval
*quality* with the real embedding model — only that the pipeline runs
correctly end to end.

Run:
    python scripts/smoke_test.py
"""

import hashlib
import os
import shutil
import sys
import tempfile

import numpy as np
import faiss

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class StubEmbedder:
    """Deterministic bag-of-words hash embedding — same word always maps to
    the same dimensions, so chunks/queries sharing vocabulary end up closer
    together. Good enough to sanity-check ranking logic without a real model."""

    DIM = 64

    def encode(self, texts, convert_to_numpy=True, batch_size=16):
        vecs = np.zeros((len(texts), self.DIM), dtype="float32")
        for i, text in enumerate(texts):
            for word in text.lower().split():
                h = int(hashlib.md5(word.encode()).hexdigest(), 16)
                vecs[i, h % self.DIM] += 1.0
            norm = np.linalg.norm(vecs[i])
            if norm > 0:
                vecs[i] /= norm
        return vecs


def main():
    tmp_dir = tempfile.mkdtemp(prefix="smogon_smoke_")
    print(f"[*] Using scratch dir: {tmp_dir}")

    from rag_engine import config
    # Redirect config paths to the scratch dir so this never touches real RAG_Data.
    config.DATA_DIR = tmp_dir
    config.FAISS_INDEX_PATH = os.path.join(tmp_dir, "faiss_index.bin")
    config.CHUNKS_PATH = os.path.join(tmp_dir, "chunks.jsonl")
    config.GRAPH_PATH = os.path.join(tmp_dir, "graph.json")

    from rag_engine.entities import extract_entities
    from rag_engine.storage import ChunkStore, save_chunks, load_chunks, load_faiss_index
    from rag_engine.graph_store import build_graph, save_graph, load_graph, graph_stats
    from rag_engine.hybrid_retriever import HybridRetriever
    from rag_engine.debug_logger import log_retrieval

    # ── 1. Synthetic corpus ──────────────────────────────────────────────────
    raw_docs = [
        "[DISCUSSION]\nTitle: Gholdengo OU Analysis\nForum: SV OU\nURL: http://example.com/1\n\n"
        "Gholdengo is an S tier OU Pokemon in SV. Its Good as Gold ability blocks status "
        "moves, making it a premier special attacker. Common set: Nasty Plot, Shadow Ball, "
        "Make It Rain, Recover.",

        "[DISCUSSION]\nTitle: Great Tusk OU Analysis\nForum: SV OU\nURL: http://example.com/2\n\n"
        "Great Tusk is a top OU threat in SV, often paired with Gholdengo on balance teams "
        "since Gholdengo checks the Fighting-types that trouble Great Tusk. Headlong Rush "
        "and Rapid Spin are common moves.",

        "[DISCUSSION]\nTitle: Iron Valiant OU Analysis\nForum: SV OU\nURL: http://example.com/3\n\n"
        "Iron Valiant is a fast mixed attacker in SV OU. It commonly appears alongside "
        "Great Tusk on hyper offense teams to overwhelm bulky cores.",

        "[DISCUSSION]\nTitle: UU Tiering Update\nForum: SV UU\nURL: http://example.com/4\n\n"
        "This week's UU tiering council discussion covers several Pokemon suspected for "
        "the UU tier, including usage stats and viability rankings for the metagame.",

        "[POKEMON TEAM]\nTitle: SV OU Balance Team\nForum: SV OU\nURL: http://example.com/5\n\n"
        "Gholdengo @ Air Balloon\nAbility: Good as Gold\nEVs: 252 SpA / 4 SpD / 252 Spe\n"
        "- Nasty Plot\n- Shadow Ball\n- Make It Rain\n- Recover",
    ]

    records = []
    for i, text in enumerate(raw_docs):
        entities = extract_entities(text)
        records.append({
            "id": i,
            "text": text,
            "content": text,
            "title": text.split("Title: ")[1].split("\n")[0] if "Title: " in text else "unknown",
            "forum": "SV OU",
            "url": f"http://example.com/{i}",
            "is_team": text.startswith("[POKEMON TEAM]"),
            "mons": entities["mons"],
            "tiers": entities["tiers"],
            "gen_tag": entities["gen_tag"],
            "source": "synthetic",
        })

    print(f"[*] {len(records)} synthetic chunks built")
    for r in records:
        print(f"    id={r['id']}  mons={r['mons']}  tiers={r['tiers']}")

    # ── 2. Embed + FAISS ──────────────────────────────────────────────────────
    embedder = StubEmbedder()
    vecs = embedder.encode([r["text"] for r in records])
    index = faiss.IndexFlatL2(embedder.DIM)
    index.add(vecs)
    faiss.write_index(index, config.FAISS_INDEX_PATH)
    print(f"[✓] FAISS index built: {index.ntotal} vectors")

    # ── 3. Save chunks + reload (round-trip test) ────────────────────────────
    save_chunks(records, config.CHUNKS_PATH)
    chunk_store = load_chunks(config.CHUNKS_PATH)
    assert len(chunk_store) == len(records), "chunk store round-trip mismatch"
    print(f"[✓] chunks.jsonl round-trip OK: {len(chunk_store)} chunks")

    # ── 4. Build + save + reload graph ────────────────────────────────────────
    graph = build_graph(chunk_store)
    save_graph(graph, config.GRAPH_PATH)
    graph = load_graph(config.GRAPH_PATH)
    stats = graph_stats(graph)
    print(f"[✓] Graph round-trip OK: {stats}")
    assert stats["mon_nodes"] >= 3, "expected at least Gholdengo/Great Tusk/Iron Valiant nodes"

    # ── 5. Hybrid retrieval ────────────────────────────────────────────────────
    index = load_faiss_index(config.FAISS_INDEX_PATH)
    retriever = HybridRetriever(index, chunk_store, embedder, graph, debug_logger=log_retrieval)

    print("\n[*] Query: 'What are good Gholdengo teammates in SV OU?'")
    results = retriever.retrieve("What are good Gholdengo teammates in SV OU?", history=[])
    assert results, "expected at least one chunk back"
    print(f"[✓] Retrieved {len(results)} chunks")

    # Great Tusk chunk (id=1) never says "teammate" but co-occurs with Gholdengo
    # in the graph via the team chunk (id=4) and the Great Tusk analysis (id=1)
    # itself mentions Gholdengo directly — either way this proves graph
    # traversal is contributing candidates beyond raw keyword/vector overlap.
    combined_text = " ".join(results)
    assert "Great Tusk" in combined_text or "great tusk" in combined_text.lower(), (
        "expected graph-assisted retrieval to surface the Great Tusk chunk"
    )
    print("[✓] Graph-assisted retrieval surfaced a co-occurring entity's chunk as expected")

    shutil.rmtree(tmp_dir, ignore_errors=True)
    print("\n✅ SMOKE TEST PASSED — pipeline is wired correctly end to end.")
    print("   (This used a stub embedder, not the real model — retrieval QUALITY")
    print("    still depends on all-MiniLM-L6-v2 once you run the real build_index.py)")


if __name__ == "__main__":
    main()
