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

import faiss

from . import config


class ChunkStore:
    """In-memory chunk store backed by chunks.jsonl on disk."""

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
        """Lookup by FAISS row position (0..N-1), which equals chunk['id'] as
        long as the store was built in order — asserted at load time."""
        if 0 <= idx < len(self._chunks):
            return self._chunks[idx]
        return None

    @property
    def chunks(self) -> list[dict]:
        return self._chunks


def load_chunks(path: str | None = None) -> ChunkStore:
    path = path or config.CHUNKS_PATH
    if not os.path.exists(path):
        raise FileNotFoundError(
            f"Chunk store not found at {path}. Run scripts/build_index.py first "
            f"(or scripts/migrate_pkl_to_jsonl.py if you have an existing docs.pkl)."
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
    # FAISS row i must correspond to chunks[i] — build_index.py guarantees this
    # by writing chunks in the same order they were embedded.
    for i, c in enumerate(chunks):
        if c["id"] != i:
            raise ValueError(
                f"chunks.jsonl is out of order or has gaps at line {i} "
                f"(id={c['id']}). FAISS row lookups require id == row index. "
                f"Rebuild with scripts/build_index.py."
            )
    return ChunkStore(chunks)


def save_chunks(records: list[dict], path: str | None = None) -> None:
    path = path or config.CHUNKS_PATH
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for rec in records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def load_faiss_index(path: str | None = None):
    path = path or config.FAISS_INDEX_PATH
    if not os.path.exists(path):
        raise FileNotFoundError(f"FAISS index not found at {path}. Run scripts/build_index.py first.")
    return faiss.read_index(path)
