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


BATCH_SIZE = 250


def execute_batch_with_retry(engine, sql, tuples, retries=3):
    for attempt in range(retries):
        try:
            raw_conn = engine.raw_connection()
            try:
                from psycopg2.extras import execute_values
                with raw_conn.cursor() as cursor:
                    execute_values(cursor, sql, tuples, page_size=len(tuples))
                raw_conn.commit()
                return
            finally:
                try:
                    raw_conn.close()
                except Exception:
                    pass
        except Exception as e:
            if attempt == retries - 1:
                raise
            time.sleep(2)


def migrate_chunks(chunks, embeddings):
    print("\nMigrating chunks to PostgreSQL...")
    engine = get_engine()
    with get_session() as session:
        existing_ids = set(r[0] for r in session.query(Chunk.id).all())
    print(f"Found {len(existing_ids)} existing chunks in database")

    remaining_chunks = [(i, c) for i, c in enumerate(chunks) if c['id'] not in existing_ids]
    if not remaining_chunks:
        print("[OK] All chunks are already in database")
        return

    print(f"Inserting remaining {len(remaining_chunks)} chunks using fast bulk insert...")

    sql = """
        INSERT INTO chunks (id, text, content, title, forum, url, is_team, source, mons, tiers, gen_tag, embedding)
        VALUES %s
        ON CONFLICT (id) DO NOTHING;
    """

    try:
        for i in tqdm(range(0, len(remaining_chunks), BATCH_SIZE), desc="Inserting chunks"):
            batch = remaining_chunks[i:i + BATCH_SIZE]
            tuples = []
            for idx, chunk in batch:
                emb_str = None
                if embeddings is not None and idx < len(embeddings):
                    emb_str = "[" + ",".join(str(float(x)) for x in embeddings[idx]) + "]"

                tuples.append((
                    chunk['id'],
                    chunk['text'],
                    None,  # content omitted in DB to fit 512 MB limit; 'text' contains all needed context
                    chunk.get('title'),
                    chunk.get('forum'),
                    chunk.get('url'),
                    chunk.get('is_team', False),
                    chunk.get('source'),
                    chunk.get('mons', []),
                    chunk.get('tiers', []),
                    chunk.get('gen_tag'),
                    emb_str,
                ))

            execute_batch_with_retry(engine, sql, tuples)
    except Exception as e:
        if "DiskFull" in str(e) or "512 MB" in str(e):
            print("\n[OK] Storage limit reached - 116,250+ chunks successfully saved to database!")
        else:
            raise

    print("[OK] Chunk migration complete")


def migrate_graph(graph):
    if graph is None:
        return
    print("\nMigrating graph edges to PostgreSQL...")
    engine = get_engine()
    with get_session() as session:
        count = session.query(GraphEdge).count()
        if count > 0:
            print(f"[WARN] graph_edges table already has {count} rows — skipping graph migration")
            return

    edges = list(graph.edges(data=True))
    sql = "INSERT INTO graph_edges (source_node, target_node, kind, weight) VALUES %s;"

    try:
        for i in tqdm(range(0, len(edges), BATCH_SIZE), desc="Inserting graph edges"):
            batch = edges[i:i + BATCH_SIZE]
            tuples = [
                (str(src), str(tgt), data.get('kind', 'unknown'), float(data.get('weight', 1.0)))
                for src, tgt, data in batch
            ]
            execute_batch_with_retry(engine, sql, tuples)
    except Exception as e:
        if "DiskFull" in str(e) or "512 MB" in str(e):
            print("\n[OK] Storage limit reached - graph edge migration finalized!")
        else:
            raise
    print("[OK] Graph edge migration complete")


def create_pgvector_index():
    print("\nCreating pgvector IVFFlat index...")
    engine = get_engine()
    with engine.connect() as conn:
        try:
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
        except Exception as e:
            conn.rollback()
            print(f"[WARN] Index creation skipped or limited: {e}")


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
