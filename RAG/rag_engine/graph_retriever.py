"""
rag_engine.graph_retriever
──────────────────────────────
Given a parsed query (mon/tier), traverses the entity graph to find:
  1. Chunks directly connected to the mentioned entity/entities (score ~1.0)
  2. Chunks connected to entities that strongly co-occur with them — e.g.
     querying "Gholdengo" also pulls in chunks about Pokémon frequently
     discussed alongside it, at a decayed score.

This is what lets the hybrid retriever surface relevant chunks that never
contain the literal query text, which pure vector similarity can miss.
"""

from . import config
from .graph_store import mon_node, tier_node, CHUNK_PREFIX


class GraphRetriever:
    def __init__(self, graph, chunk_store):
        self.graph = graph
        self.chunk_store = chunk_store

    def _chunks_of(self, entity_node: str, limit: int) -> list[str]:
        if entity_node not in self.graph:
            return []
        chunk_nodes = [
            n for n in self.graph.neighbors(entity_node)
            if n.startswith(CHUNK_PREFIX)
        ]
        return chunk_nodes[:limit]

    def _neighbor_entities(self, entity_node: str, limit: int) -> list[tuple[str, float]]:
        """Other entity nodes co-occurring with this one, sorted by edge weight."""
        if entity_node not in self.graph:
            return []
        neighbors = []
        for n in self.graph.neighbors(entity_node):
            if n.startswith(CHUNK_PREFIX):
                continue
            edge = self.graph[entity_node][n]
            if edge.get("kind") != "cooccurs":
                continue
            neighbors.append((n, edge.get("weight", 1)))
        neighbors.sort(key=lambda x: x[1], reverse=True)
        return neighbors[:limit]

    def search(self, parsed: dict) -> dict[int, float]:
        """
        Returns {chunk_id: graph_score} in roughly the same 0..1 range as the
        vector retriever's normalized similarity, so the hybrid combiner can
        weight them together meaningfully.
        """
        scores: dict[int, float] = {}

        primary_nodes = []
        if parsed.get("mon"):
            primary_nodes.append(mon_node(parsed["mon"]))
        if parsed.get("tier"):
            primary_nodes.append(tier_node(parsed["tier"]))

        for entity_node in primary_nodes:
            # Direct hits: chunks that mention this entity outright.
            for cnode in self._chunks_of(entity_node, config.GRAPH_MAX_CHUNKS_PER_ENTITY):
                cid = int(cnode.split(":", 1)[1])
                scores[cid] = max(scores.get(cid, 0.0), 1.0)

            # One-hop expansion: chunks reached via a strongly co-occurring entity.
            for neighbor_node, weight in self._neighbor_entities(entity_node, config.GRAPH_MAX_NEIGHBOR_ENTITIES):
                saturating_weight = weight / (weight + 3)  # bounded (0,1), rewards well-connected neighbors
                neighbor_score = config.GRAPH_NEIGHBOR_SCORE_DECAY * saturating_weight
                for cnode in self._chunks_of(neighbor_node, config.GRAPH_MAX_CHUNKS_PER_ENTITY):
                    cid = int(cnode.split(":", 1)[1])
                    scores[cid] = max(scores.get(cid, 0.0), neighbor_score)

        return scores
