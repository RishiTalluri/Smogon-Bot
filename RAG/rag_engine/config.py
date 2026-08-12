"""
rag_engine.config
──────────────────
Single source of truth for paths and tunables. Previously these were scattered
as module-level constants at the top of Bot.py; centralising them means
Server.py, Bot.py, and the index-build script all agree on the same values
without importing from each other.
"""

import os
from dotenv import load_dotenv

load_dotenv()

# ─── PATHS ─────────────────────────────────────────────────────────────────────
# Resolved relative to this file so it works regardless of the current working
# directory the process was launched from (Bot.py used hardcoded ..\ paths that
# only worked when run from inside RAG/).
_THIS_DIR   = os.path.dirname(os.path.abspath(__file__))
RAG_DIR     = os.path.dirname(_THIS_DIR)                 # .../RAG
DATA_DIR    = os.path.join(RAG_DIR, "RAG_Data")

FAISS_INDEX_PATH = os.path.join(DATA_DIR, "faiss_index.bin")
CHUNKS_PATH       = os.path.join(DATA_DIR, "chunks.jsonl")   # replaces docs.pkl
GRAPH_PATH         = os.path.join(DATA_DIR, "graph.json")     # entity co-occurrence graph

# Legacy path, only read by scripts/migrate_pkl_to_jsonl.py
LEGACY_CHUNKS_PKL_PATH = os.path.join(DATA_DIR, "docs.pkl")

# ─── MODELS ────────────────────────────────────────────────────────────────────
EMBED_MODEL = "all-MiniLM-L6-v2"

GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
GROQ_MODEL   = os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile")

DATABASE_URL = os.environ.get('DATABASE_URL', '')
JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY', 'dev-secret-change-me')
JWT_EXPIRY_HOURS = int(os.environ.get('JWT_EXPIRY_HOURS', '24'))

QDRANT_URL = os.environ.get("QDRANT_URL", "")
QDRANT_API_KEY = os.environ.get("QDRANT_API_KEY", "")
QDRANT_COLLECTION = os.environ.get("QDRANT_COLLECTION", "smogon_chunks")

# ─── RETRIEVAL TUNABLES ─────────────────────────────────────────────────────────
TOP_K              = 50      # FAISS candidates per query variant
FINAL_TOP_K        = 10      # chunks sent to the LLM after hybrid reranking
MIN_CHUNK_WORDS    = 15      # drop micro-chunks
SIMILARITY_CUTOFF  = 2.2     # max L2 distance to accept a vector candidate
MAX_CONTEXT_CHARS  = 14000   # total chars of context sent to the LLM

# Per-intent TOP_K overrides — some intents need broader search
INTENT_TOP_K = {
    "tiering":      70,
    "tier_explain": 70,
    "general":      70,
    "viability":    60,
    "usage":        60,
}

MAX_HISTORY = 6  # conversation turns to keep (3 user + 3 bot)

# ─── HYBRID SCORING WEIGHTS ─────────────────────────────────────────────────────
# final_score = (vector_sim * W_VECTOR) + (keyword_score * W_KEYWORD) + (graph_score * W_GRAPH)
# Weights don't need to sum to 1 — they're relative importance, not a probability.
HYBRID_WEIGHT_VECTOR  = 0.45
HYBRID_WEIGHT_KEYWORD = 0.35
HYBRID_WEIGHT_GRAPH   = 0.20

# ─── GRAPHRAG TUNABLES ───────────────────────────────────────────────────────────
GRAPH_MAX_NEIGHBOR_ENTITIES = 5     # how many co-occurring entities to expand into
GRAPH_NEIGHBOR_SCORE_DECAY  = 0.6   # multiplier applied to chunks reached via a neighbor, not the entity itself
GRAPH_MAX_CHUNKS_PER_ENTITY = 25    # cap how many chunks one entity node can contribute

# ─── DEBUG ───────────────────────────────────────────────────────────────────────
# Always prints retrieval internals (which chunks, which retriever, scores) to
# the server's own terminal/stdout. Never sent in any API response — Server.py
# only ever returns {answer, chunks_used, corrected_mon} to the client.
SHOW_RETRIEVAL_DEBUG = os.environ.get("SHOW_RETRIEVAL_DEBUG", "1") != "0"
