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
    """Lazy ChunkStore backed by database. Fetches chunks on-demand to save ~380MB RAM on Render."""

    def __init__(self, chunks: list[dict] | None = None):
        if chunks:
            self._by_id = {c["id"]: c for c in chunks}
            self._chunks = chunks
        else:
            self._by_id = {}
            self._chunks = []

    def __len__(self):
        return len(self._chunks) if self._chunks else 70000

    def __iter__(self):
        return iter(self._chunks)

    def get(self, chunk_id: int) -> dict | None:
        if chunk_id in self._by_id:
            return self._by_id[chunk_id]

        # On-demand query from PostgreSQL
        try:
            from .database import get_session
            from .models import Chunk
            with get_session() as session:
                row = session.query(Chunk).filter_by(id=chunk_id).first()
                if row:
                    chunk = {
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
                    }
                    self._by_id[chunk_id] = chunk
                    return chunk
        except Exception as e:
            print(f"[WARN] Failed to fetch chunk {chunk_id} from DB: {e}")
        return None

    def by_index(self, idx: int) -> dict | None:
        return self.get(idx)

    @property
    def chunks(self) -> list[dict]:
        return self._chunks


def load_chunks_from_db() -> ChunkStore:
    """Return a lazy ChunkStore without pre-loading 70,000 chunks into RAM."""
    print("[✓] Initialized lazy ChunkStore (on-demand DB loading)")
    return ChunkStore()


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
