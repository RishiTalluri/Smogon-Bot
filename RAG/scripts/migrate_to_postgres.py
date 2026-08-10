"""
scripts/migrate_to_postgres.py
───────────────────────────────
One-time migration: loads chunks.jsonl + faiss_index.bin + graph.json from
RAG_Data/ and inserts everything into PostgreSQL.

Run: python scripts/migrate_to_postgres.py
"""
import json
import os
import sys
import time

import numpy as np
from tqdm import tqdm

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rag_engine import config
from rag_engine.database import get_engine, get_session, create_tables
from rag_engine.models import Chunk, GraphEdge
from sqlalchemy import text

BATCH_SIZE = 500


def load_chunks_file():
    path = config.CHUNKS_PATH
    if not os.path.exists(path):
        print(f"[ERROR] {path} not found")
        sys.exit(1)
    chunks = []
    with open(path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line:
                chunks.append(json.loads(line))
    print(f"Loaded {len(chunks)} chunks from {path}")
    return chunks


def load_embeddings():
    path = config.FAISS_INDEX_PATH
    if not os.path.exists(path):
        print(f"[WARN] {path} not found — embeddings will need to be recomputed")
        return None
    import faiss
    index = faiss.read_index(path)
    n = index.ntotal
    dim = index.d
    embeddings = np.zeros((n, dim), dtype='float32')
    # Reconstruct all vectors from the FAISS index
    for i in range(n):
        embeddings[i] = index.reconstruct(i)
    print(f"Loaded {n} embeddings (dim={dim}) from FAISS index")
    return embeddings


def load_graph_file():
    path = config.GRAPH_PATH
    if not os.path.exists(path):
        print(f"[WARN] {path} not found — graph edges will be skipped")
        return None
    import networkx as nx
    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    g = nx.node_link_graph(data, edges='edges')
    print(f"Loaded graph: {g.number_of_nodes()} nodes, {g.number_of_edges()} edges")
    return g


def migrate_chunks(chunks, embeddings):
    print("\nMigrating chunks to PostgreSQL...")
    with get_session() as session:
        # Check if chunks already exist
        count = session.query(Chunk).count()
        if count > 0:
            print(f"[WARN] chunks table already has {count} rows — skipping chunk migration")
            return

    with get_session() as session:
        for i in tqdm(range(0, len(chunks), BATCH_SIZE), desc="Inserting chunks"):
            batch = chunks[i:i + BATCH_SIZE]
            for j, chunk in enumerate(batch):
                idx = i + j
                emb = embeddings[idx].tolist() if embeddings is not None and idx < len(embeddings) else None
                row = Chunk(
                    id=chunk['id'],
                    text=chunk['text'],
                    content=chunk.get('content'),
                    title=chunk.get('title'),
                    forum=chunk.get('forum'),
                    url=chunk.get('url'),
                    is_team=chunk.get('is_team', False),
                    source=chunk.get('source'),
                    mons=chunk.get('mons', []),
                    tiers=chunk.get('tiers', []),
                    gen_tag=chunk.get('gen_tag'),
                    embedding=emb,
                )
                session.add(row)
            session.flush()
    print(f"Inserted {len(chunks)} chunks")


def migrate_graph(graph):
    if graph is None:
        return
    print("\nMigrating graph edges to PostgreSQL...")
    with get_session() as session:
        count = session.query(GraphEdge).count()
        if count > 0:
            print(f"[WARN] graph_edges table already has {count} rows — skipping graph migration")
            return

    edges = list(graph.edges(data=True))
    with get_session() as session:
        for i in tqdm(range(0, len(edges), BATCH_SIZE), desc="Inserting graph edges"):
            batch = edges[i:i + BATCH_SIZE]
            for src, tgt, data in batch:
                row = GraphEdge(
                    source_node=str(src),
                    target_node=str(tgt),
                    kind=data.get('kind', 'unknown'),
                    weight=float(data.get('weight', 1.0)),
                )
                session.add(row)
            session.flush()
    print(f"Inserted {len(edges)} graph edges")


def create_pgvector_index():
    print("\nCreating pgvector IVFFlat index...")
    engine = get_engine()
    with engine.connect() as conn:
        # Count chunks for lists parameter
        result = conn.execute(text("SELECT COUNT(*) FROM chunks WHERE embedding IS NOT NULL"))
        chunk_count = result.scalar()
        # IVFFlat lists: sqrt(n) is a good default
        lists = max(10, int(chunk_count ** 0.5))
        print(f"  chunks with embeddings: {chunk_count}, using {lists} IVFFlat lists")
        conn.execute(text(f"DROP INDEX IF EXISTS ix_chunks_embedding"))
        conn.execute(text(
            f"CREATE INDEX ix_chunks_embedding ON chunks "
            f"USING ivfflat (embedding vector_l2_ops) WITH (lists = {lists})"
        ))
        conn.commit()
    print("pgvector index created")


def main():
    start = time.time()

    print("Creating tables...")
    create_tables()

    chunks = load_chunks_file()
    embeddings = load_embeddings()
    graph = load_graph_file()

    migrate_chunks(chunks, embeddings)
    migrate_graph(graph)
    create_pgvector_index()

    elapsed = time.time() - start
    print(f"\n Migration complete in {elapsed:.0f}s")


if __name__ == '__main__':
    main()
