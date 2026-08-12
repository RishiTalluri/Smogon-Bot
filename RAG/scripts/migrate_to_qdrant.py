"""
scripts/migrate_to_qdrant.py
────────────────────────────
One-time script: Uploads ALL 204,936 chunks + 384-dim embeddings from local files
(chunks.jsonl + faiss_index.bin) directly into Qdrant Cloud.

Usage:
  set QDRANT_URL=https://xxx.cloud.qdrant.io
  set QDRANT_API_KEY=your-qdrant-api-key
  python scripts/migrate_to_qdrant.py
"""
import json
import os
import sys
import time

import numpy as np
from tqdm import tqdm

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rag_engine import config

BATCH_SIZE = 250

def upsert_with_retry(client, collection_name, points, retries=4):
    for attempt in range(retries):
        try:
            client.upsert(collection_name=collection_name, points=points)
            return
        except Exception as e:
            if attempt == retries - 1:
                raise
            time.sleep(3)


def load_chunks():
    path = config.CHUNKS_PATH
    if not os.path.exists(path):
        print(f"[ERROR] {path} not found")
        sys.exit(1)
    chunks = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                chunks.append(json.loads(line))
    print(f"Loaded {len(chunks)} chunks from {path}")
    return chunks


def load_embeddings():
    path = config.FAISS_INDEX_PATH
    if not os.path.exists(path):
        print(f"[ERROR] {path} not found")
        sys.exit(1)
    import faiss
    index = faiss.read_index(path)
    n = index.ntotal
    dim = index.d
    embeddings = np.zeros((n, dim), dtype="float32")
    for i in range(n):
        embeddings[i] = index.reconstruct(i)
    print(f"Loaded {n} embeddings (dim={dim}) from FAISS index")
    return embeddings


def main():
    qdrant_url = os.environ.get("QDRANT_URL") or config.QDRANT_URL
    qdrant_key = os.environ.get("QDRANT_API_KEY") or config.QDRANT_API_KEY
    collection_name = config.QDRANT_COLLECTION

    if not qdrant_url or not qdrant_key:
        print("[ERROR] QDRANT_URL and QDRANT_API_KEY environment variables are required.")
        sys.exit(1)

    from qdrant_client import QdrantClient
    from qdrant_client.models import Distance, VectorParams, PointStruct

    print(f"Connecting to Qdrant Cloud: {qdrant_url} ...")
    client = QdrantClient(url=qdrant_url, api_key=qdrant_key, timeout=120)

    # Check if collection exists or recreate
    collections = [c.name for c in client.get_collections().collections]
    if collection_name not in collections:
        print(f"Creating Qdrant collection '{collection_name}' (dim=384, Cosine)...")
        client.create_collection(
            collection_name=collection_name,
            vectors_config=VectorParams(size=384, distance=Distance.COSINE),
        )
    else:
        print(f"Collection '{collection_name}' already exists in Qdrant.")

    chunks = load_chunks()
    embeddings = load_embeddings()

    start_time = time.time()
    print(f"\nUploading {len(chunks)} points to Qdrant Cloud...")

    for i in tqdm(range(0, len(chunks), BATCH_SIZE), desc="Uploading to Qdrant"):
        batch_chunks = chunks[i : i + BATCH_SIZE]
        points = []
        for j, chunk in enumerate(batch_chunks):
            idx = i + j
            vector = embeddings[idx].tolist() if idx < len(embeddings) else [0.0] * 384
            points.append(
                PointStruct(
                    id=chunk["id"],
                    vector=vector,
                    payload={
                        "title": chunk.get("title", ""),
                        "forum": chunk.get("forum", ""),
                        "url": chunk.get("url", ""),
                        "is_team": chunk.get("is_team", False),
                        "mons": chunk.get("mons", []),
                        "tiers": chunk.get("tiers", []),
                        "gen_tag": chunk.get("gen_tag", ""),
                    },
                )
            )

        upsert_with_retry(client, collection_name, points)

    elapsed = time.time() - start_time
    print(f"\n[OK] Uploaded {len(chunks)} chunks to Qdrant Cloud in {elapsed:.0f}s!")


if __name__ == "__main__":
    main()
