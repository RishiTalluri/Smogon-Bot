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
    path = path or config.GRAPH_PATH
    os.makedirs(os.path.dirname(path), exist_ok=True)
    data = nx.node_link_data(g, edges="edges")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f)


def load_graph(path: str | None = None) -> nx.Graph:
    path = path or config.GRAPH_PATH
    if not os.path.exists(path):
        raise FileNotFoundError(
            f"Graph not found at {path}. Run scripts/build_index.py first."
        )
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return nx.node_link_graph(data, edges="edges")


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
