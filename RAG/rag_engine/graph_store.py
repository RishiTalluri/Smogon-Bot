"""
rag_engine.graph_store
──────────────────────────
Builds a lightweight knowledge graph over the corpus: Pokémon and tier
entities as nodes, chunks as nodes, "mentions" edges connecting a chunk to
every entity it references, and weighted co-occurrence edges connecting
entities that appear together in the same chunk.

This is a scoped, practical GraphRAG — not full Microsoft-GraphRAG (no LLM
entity extraction, no community summarisation). It's built entirely from the
regex-based entity extraction in entities.py, which is cheap enough to run at
index-build time over the whole corpus and fast enough to query at request
time with plain graph traversal. What it buys us: a query about "Gholdengo"
can also surface chunks that never say "Gholdengo" by name but are strongly
co-occurring — e.g. a thread about its most common teammates or checks —
which pure vector similarity on the literal query text tends to miss.

Serialized as JSON (node-link format), not pickle — inspectable, portable,
no arbitrary-code-execution surface.
"""

import json
import os

import networkx as nx

from . import config

CHUNK_PREFIX = "chunk:"
MON_PREFIX   = "mon:"
TIER_PREFIX  = "tier:"


def chunk_node(cid: int) -> str:
    return f"{CHUNK_PREFIX}{cid}"


def mon_node(name: str) -> str:
    return f"{MON_PREFIX}{name}"


def tier_node(tier: str) -> str:
    return f"{TIER_PREFIX}{tier}"


def build_graph(chunk_store, show_progress: bool = True) -> nx.Graph:
    """
    One pass over every chunk:
      - add a chunk node
      - add/connect an entity node for each mon and tier it mentions ("mentions" edge)
      - increment a co-occurrence edge weight between every pair of entities
        that appear together in this chunk
    """
    g = nx.Graph()

    iterator = chunk_store
    if show_progress:
        from tqdm import tqdm
        iterator = tqdm(chunk_store, total=len(chunk_store), desc="Building entity graph", unit="chunk")

    for chunk in iterator:
        cid = chunk["id"]
        cnode = chunk_node(cid)
        g.add_node(cnode, type="chunk")

        entity_nodes = []
        for mon in chunk.get("mons", []):
            node = mon_node(mon)
            g.add_node(node, type="mon", label=mon)
            g.add_edge(cnode, node, kind="mentions")
            entity_nodes.append(node)

        for tier in chunk.get("tiers", []):
            node = tier_node(tier)
            g.add_node(node, type="tier", label=tier)
            g.add_edge(cnode, node, kind="mentions")
            entity_nodes.append(node)

        # Co-occurrence: every pair of entities mentioned in the same chunk
        # gets (or strengthens) a weighted edge between them.
        for i in range(len(entity_nodes)):
            for j in range(i + 1, len(entity_nodes)):
                a, b = entity_nodes[i], entity_nodes[j]
                if g.has_edge(a, b) and g[a][b].get("kind") == "cooccurs":
                    g[a][b]["weight"] += 1
                else:
                    g.add_edge(a, b, kind="cooccurs", weight=1)

    return g


def save_graph(g: nx.Graph, path: str | None = None) -> None:
    from .database import get_session
    from .models import GraphEdge

    with get_session() as session:
        session.query(GraphEdge).delete()
        for u, v, d in g.edges(data=True):
            session.add(GraphEdge(
                source_node=u,
                target_node=v,
                kind=d.get("kind", ""),
                weight=d.get("weight", 1.0)
            ))


def load_graph(path: str | None = None) -> nx.Graph:
    from .database import get_session
    from .models import GraphEdge

    g = nx.Graph()
    with get_session() as session:
        edges = session.query(GraphEdge).all()
        for e in edges:
            if e.source_node.startswith("chunk:"):
                g.add_node(e.source_node, type="chunk")
            elif e.source_node.startswith("mon:"):
                g.add_node(e.source_node, type="mon", label=e.source_node[4:])
            elif e.source_node.startswith("tier:"):
                g.add_node(e.source_node, type="tier", label=e.source_node[5:])

            if e.target_node.startswith("chunk:"):
                g.add_node(e.target_node, type="chunk")
            elif e.target_node.startswith("mon:"):
                g.add_node(e.target_node, type="mon", label=e.target_node[4:])
            elif e.target_node.startswith("tier:"):
                g.add_node(e.target_node, type="tier", label=e.target_node[5:])

            g.add_edge(e.source_node, e.target_node, kind=e.kind, weight=e.weight)
    return g


def graph_stats(g: nx.Graph) -> dict:
    mon_nodes  = [n for n, d in g.nodes(data=True) if d.get("type") == "mon"]
    tier_nodes = [n for n, d in g.nodes(data=True) if d.get("type") == "tier"]
    chunk_nodes = [n for n, d in g.nodes(data=True) if d.get("type") == "chunk"]
    return {
        "chunk_nodes": len(chunk_nodes),
        "mon_nodes": len(mon_nodes),
        "tier_nodes": len(tier_nodes),
        "edges": g.number_of_edges(),
    }
