"""
rag_engine.vector_retriever
──────────────────────────────
The "RAG" half of the hybrid pipeline: dense vector search over FAISS.
Batch-encodes every query variant in one call and merges results, deduped by
chunk id (previously deduped by md5-hashing the full chunk text on every
request — id-based dedup is both simpler and cheaper since ids are stable).
"""

import numpy as np
from sqlalchemy import text

from .database import get_session
from . import config


class VectorRetriever:
    def __init__(self, embedder):
        self.embedder = embedder

    def search(self, query_variants: list[str], top_k: int = config.TOP_K) -> dict[int, float]:
        """Embed each query variant and search Qdrant Cloud (or pgvector). Returns {chunk_id: distance}."""
        all_distances: dict[int, float] = {}

        if hasattr(self.embedder, "embed"):
            embeddings = [list(vec) for vec in self.embedder.embed(query_variants)]
        else:
            embeddings = self.embedder.encode(query_variants)

        # ── 1. Query Qdrant Cloud if configured ──────────────────────────────
        if config.QDRANT_URL:
            try:
                from qdrant_client import QdrantClient
                q_client = QdrantClient(url=config.QDRANT_URL, api_key=config.QDRANT_API_KEY, timeout=10)
                for emb in embeddings:
                    vec_list = [float(x) for x in emb]
                    results = q_client.search(
                        collection_name=config.QDRANT_COLLECTION,
                        query_vector=vec_list,
                        limit=top_k,
                    )
                    for res in results:
                        cid = int(res.id)
                        # Qdrant score is similarity score (1.0 = identical, 0 = different)
                        # We convert similarity to distance metric (1 - score) for consistent normalize()
                        dist = max(0.0, 1.0 - float(res.score))
                        if cid not in all_distances or dist < all_distances[cid]:
                            all_distances[cid] = dist
                return all_distances
            except Exception as e:
                print(f"[WARN] Qdrant search failed, falling back to pgvector: {e}")

        # ── 2. Fallback to PostgreSQL pgvector ───────────────────────────────
        with get_session() as session:
            for emb in embeddings:
                vec_str = "[" + ",".join(str(float(x)) for x in emb) + "]"
                sql = text(
                    "SELECT id, embedding <-> :vec AS distance "
                    "FROM chunks "
                    "WHERE embedding IS NOT NULL "
                    "ORDER BY distance "
                    "LIMIT :k"
                )
                rows = session.execute(sql, {"vec": vec_str, "k": top_k}).fetchall()
                for row in rows:
                    cid, dist = row[0], float(row[1])
                    if cid not in all_distances or dist < all_distances[cid]:
                        all_distances[cid] = dist

        return all_distances

    @staticmethod
    def normalize(distances: dict[int, float]) -> dict[int, float]:
        """Convert L2 distances to 0..1 similarity scores (higher = better)."""
        if not distances:
            return {}
        max_dist = max(distances.values())
        min_dist = min(distances.values())
        spread = max_dist - min_dist
        if spread < 1e-9:
            return {cid: 1.0 for cid in distances}
        return {
            cid: 1.0 - (dist - min_dist) / spread
            for cid, dist in distances.items()
        }
