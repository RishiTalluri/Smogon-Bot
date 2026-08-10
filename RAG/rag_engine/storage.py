"""
rag_engine.storage
─────────────────────
Replaces docs.pkl (a flat pickled list of opaque strings) with chunks.jsonl:
one JSON object per line, each carrying structured metadata alongside the
chunk text. This is what makes GraphRAG possible — the graph builder needs
to know *which Pokémon/tiers a chunk mentions*, and previously that required
re-parsing the raw string on every load. Now it's just a field.

Why JSONL over pickle:
  - Human-readable and git-diffable — you can `head chunks.jsonl` and see it.
  - No arbitrary-code-execution surface from unpickling (chunks.jsonl is safe
    to hand-edit, inspect, or load in a language that isn't Python).
  - Trivial to append/stream without loading the whole file into memory if the
    corpus grows large.
  - Each line is independently valid JSON, so a corrupted trailing line only
    loses one chunk instead of the whole file failing to unpickle.

FAISS's own .bin format is untouched — that's not pickle, it's FAISS's native
serialization and remains the right tool for the vector index itself.
"""

import json
import os

from . import config


class ChunkStore:
    """In-memory chunk store, loaded from PostgreSQL at boot."""

    def __init__(self, chunks: list[dict]):
        self._chunks = chunks
        self._by_id = {c["id"]: c for c in chunks}

    def __len__(self):
        return len(self._chunks)

    def __iter__(self):
        return iter(self._chunks)

    def get(self, chunk_id: int) -> dict | None:
        return self._by_id.get(chunk_id)

    def by_index(self, idx: int) -> dict | None:
        if 0 <= idx < len(self._chunks):
            return self._chunks[idx]
        return None

    @property
    def chunks(self) -> list[dict]:
        return self._chunks


def load_chunks_from_db() -> ChunkStore:
    """Load all chunks from PostgreSQL into memory."""
    from .database import get_session
    from .models import Chunk

    with get_session() as session:
        rows = session.query(Chunk).order_by(Chunk.id).all()
        chunks = []
        for row in rows:
            chunks.append({
                "id": row.id,
                "text": row.text,
                "content": row.content,
                "title": row.title,
                "forum": row.forum,
                "url": row.url,
                "is_team": row.is_team,
                "source": row.source,
                "mons": row.mons or [],
                "tiers": row.tiers or [],
                "gen_tag": row.gen_tag,
            })
    if not chunks:
        print(
            "[WARN] No chunks found in the database. "
            "Run scripts/migrate_to_postgres.py to load data."
        )
    return ChunkStore(chunks)


# ── Legacy file-based loaders (used by migration scripts only) ────────────────

def load_chunks_from_file(path: str | None = None) -> ChunkStore:
    """Legacy: load chunks from a JSONL file. Used by migration scripts."""
    path = path or config.CHUNKS_PATH
    if not os.path.exists(path):
        raise FileNotFoundError(
            f"Chunk store not found at {path}. Run scripts/build_index.py first."
        )
    chunks = []
    with open(path, "r", encoding="utf-8") as f:
        for line_no, line in enumerate(f):
            line = line.strip()
            if not line:
                continue
            try:
                chunks.append(json.loads(line))
            except json.JSONDecodeError as e:
                print(f"[WARN] Skipping malformed line {line_no} in {path}: {e}")
    for i, c in enumerate(chunks):
        if c["id"] != i:
            raise ValueError(
                f"chunks.jsonl out of order at line {i} (id={c['id']}). "
                f"Rebuild with scripts/build_index.py."
            )
    return ChunkStore(chunks)


def save_chunks(records: list[dict], path: str | None = None) -> None:
    """Legacy: save chunks to a JSONL file."""
    path = path or config.CHUNKS_PATH
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for rec in records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def load_faiss_index(path: str | None = None):
    """Legacy: load FAISS index from file. Used by migration scripts."""
    import faiss
    path = path or config.FAISS_INDEX_PATH
    if not os.path.exists(path):
        raise FileNotFoundError(f"FAISS index not found at {path}.")
    return faiss.read_index(path)
