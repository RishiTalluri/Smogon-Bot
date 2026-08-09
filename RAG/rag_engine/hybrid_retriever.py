"""
rag_engine.hybrid_retriever
──────────────────────────────
Combines all three signals into one ranked chunk list:
  - vector similarity  (VectorRetriever — dense embedding search over FAISS)
  - keyword score        (query/tier/gen/mon term overlap, same heuristic as before)
  - graph score           (GraphRetriever — entity co-occurrence traversal)

final_score = W_VECTOR * vector_sim + W_KEYWORD * keyword_score + W_GRAPH * graph_score

Any chunk found by vector search OR graph search is a candidate; a chunk only
found by the graph gets vector_sim=0 (and vice versa), so a strong single
signal can still surface a chunk, but chunks confirmed by multiple retrievers
naturally rank higher.
"""

import re

from . import config
from .entities import GEN_MARKERS
from .vector_retriever import VectorRetriever
from .graph_retriever import GraphRetriever
from .query_parser import parse_query, expand_query


def keyword_score(text: str, query: str, parsed: dict) -> float:
    """Multi-factor keyword score: query overlap, tier/mon exact match, gen alignment."""
    tl = text.lower()
    score = 0.0

    qwords = {
        w.lower() for w in re.findall(r"[a-zA-Z]+", query)
        if len(w) > 2
    }
    if qwords:
        hits = sum(1 for w in qwords if w in tl)
        score += (hits / len(qwords)) * 0.5

    if parsed["tier"] and parsed["tier"].lower() in tl:
        score += 0.2

    user_gen = parsed["gen"].lower()
    if user_gen in ("sv", "gen9", "gen 9"):
        sv_hits  = sum(1 for m in GEN_MARKERS["sv"] if m in tl)
        old_hits = sum(1 for m in GEN_MARKERS["old"] if m in tl)
        if sv_hits > 0:
            score += 0.15
        if old_hits > 0 and sv_hits == 0:
            score -= 0.25

    if parsed["mon"] and parsed["mon"].lower() in tl:
        score += 0.15

    return score


class HybridRetriever:
    """
    The single entry point Server.py and Bot.py call. Wraps vector + graph
    retrieval, merges/reranks, and (if config.SHOW_RETRIEVAL_DEBUG) reports
    everything to a debug_logger callback for terminal-only printing.
    """

    def __init__(self, chunk_store, embedder, graph, debug_logger=None):
        self.chunk_store = chunk_store
        self.vector = VectorRetriever(embedder)
        self.graph_retriever = GraphRetriever(graph, chunk_store)
        self.debug_logger = debug_logger

    def retrieve(self, query: str, history: list[dict] | None = None) -> list[str]:
        """Returns the final list of chunk *texts* to feed to the LLM (same
        return shape as the old Bot.py retrieve(), so callers don't change)."""
        parsed = parse_query(query, history)
        variants = expand_query(parsed)
        top_k = config.INTENT_TOP_K.get(parsed["intent"], config.TOP_K)

        vector_distances = self.vector.search(variants, top_k)
        vector_sim = self.vector.normalize(vector_distances)   # {cid: 0..1, higher=better}
        graph_sim = self.graph_retriever.search(parsed)         # {cid: 0..1, higher=better}

        candidate_ids = set(vector_sim) | set(graph_sim)

        scored = []
        for cid in candidate_ids:
            chunk = self.chunk_store.get(cid)
            if chunk is None:
                continue
            text = chunk["text"]
            if len(text.split()) < config.MIN_CHUNK_WORDS:
                continue

            v_score = vector_sim.get(cid, 0.0)
            g_score = graph_sim.get(cid, 0.0)
            k_score = keyword_score(text, query, parsed)

            # A chunk found ONLY by the graph (v_score == 0) still needs to have
            # been within a sane similarity range to avoid pure-graph noise —
            # skip chunks the vector search actively rejected as too dissimilar.
            if cid in vector_distances and vector_distances[cid] > config.SIMILARITY_CUTOFF and g_score == 0:
                continue

            final = (
                config.HYBRID_WEIGHT_VECTOR * v_score
                + config.HYBRID_WEIGHT_KEYWORD * k_score
                + config.HYBRID_WEIGHT_GRAPH * g_score
            )
            scored.append({
                "id": cid,
                "text": text,
                "score": final,
                "vector_score": v_score,
                "keyword_score": k_score,
                "graph_score": g_score,
                "title": chunk.get("title", ""),
                "url": chunk.get("url", ""),
                "sources": [
                    name for name, s in
                    (("vector", v_score), ("graph", g_score)) if s > 0
                ],
            })

        scored.sort(key=lambda x: x["score"], reverse=True)

        selected, total_chars = [], 0
        for c in scored:
            if len(selected) >= config.FINAL_TOP_K:
                break
            if total_chars + len(c["text"]) > config.MAX_CONTEXT_CHARS:
                remaining = config.MAX_CONTEXT_CHARS - total_chars
                if remaining > 400:
                    truncated = dict(c)
                    truncated["text"] = c["text"][:remaining]
                    selected.append(truncated)
                break
            selected.append(c)
            total_chars += len(c["text"])

        if self.debug_logger and config.SHOW_RETRIEVAL_DEBUG:
            self.debug_logger(query, parsed, variants, scored, selected)

        return [c["text"] for c in selected]
