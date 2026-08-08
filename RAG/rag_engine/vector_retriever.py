"""
rag_engine.vector_retriever
──────────────────────────────
The "RAG" half of the hybrid pipeline: dense vector search over FAISS.
Batch-encodes every query variant in one call and merges results, deduped by
chunk id (previously deduped by md5-hashing the full chunk text on every
request — id-based dedup is both simpler and cheaper since ids are stable).
"""

import numpy as np

from . import config


class VectorRetriever:
    def __init__(self, index, chunk_store, embedder):
        self.index = index
        self.chunk_store = chunk_store
        self.embedder = embedder

    def search(self, variants: list[str], top_k: int) -> dict[int, float]:
        """
        Returns {chunk_id: best_l2_distance} for every chunk retrieved by any
        variant, keeping the smallest (best) distance seen across variants.
        """
        vecs = self.embedder.encode(variants, convert_to_numpy=True, batch_size=16).astype("float32")

        best_distance: dict[int, float] = {}
        for vec in vecs:
            distances, indices = self.index.search(vec[np.newaxis, :], top_k)
            for dist, idx in zip(distances[0], indices[0]):
                chunk = self.chunk_store.by_index(int(idx))
                if chunk is None:
                    continue
                cid = chunk["id"]
                dist = float(dist)
                if cid not in best_distance or dist < best_distance[cid]:
                    best_distance[cid] = dist
        return best_distance

    @staticmethod
    def normalize(distances: dict[int, float]) -> dict[int, float]:
        """Min-max normalise L2 distances to a 0..1 similarity score (1 = best)."""
        if not distances:
            return {}
        vals = list(distances.values())
        lo, hi = min(vals), max(vals)
        span = (hi - lo) or 1.0
        return {cid: 1.0 - (d - lo) / span for cid, d in distances.items()}
