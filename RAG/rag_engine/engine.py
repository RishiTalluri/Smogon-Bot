"""
rag_engine.engine
────────────────────
Single boot path for the whole retrieval + generation stack. Both Server.py
(long-running Flask process) and Bot.py (terminal REPL) call RagEngine.load()
once at startup and share the same interface, so there's exactly one place
that wires FAISS + chunk store + graph + embedder + Groq client together.
"""

import sys

from . import config, storage
from .graph_store import load_graph
from .hybrid_retriever import HybridRetriever
from .debug_logger import log_retrieval
from .llm import ask_groq
from .query_parser import parse_query


class RagEngine:
    def __init__(self, chunk_store, retriever: HybridRetriever, groq_client):
        self.chunk_store = chunk_store
        self.retriever = retriever
        self.groq_client = groq_client

    @classmethod
    def load(cls) -> "RagEngine":
        from groq import Groq
        from sentence_transformers import SentenceTransformer
        from .database import create_tables

        print("[*] Creating database tables if needed...")
        create_tables()

        print("[*] Loading chunk store from DB...")
        chunk_store = storage.load_chunks_from_db()
        print(f"[✓] Loaded {len(chunk_store)} chunks")

        print("[*] Loading entity graph from DB...")
        graph = load_graph()
        print(f"[✓] Graph: {graph.number_of_nodes()} nodes, {graph.number_of_edges()} edges")

        print(f"[*] Loading embedding model: {config.EMBED_MODEL} ...")
        try:
            from fastembed import TextEmbedding
            embedder = TextEmbedding(model_name="sentence-transformers/all-MiniLM-L6-v2")
            print("[✓] FastEmbed (ONNX) embedding model ready")
        except ImportError:
            from sentence_transformers import SentenceTransformer
            embedder = SentenceTransformer(config.EMBED_MODEL)
            print("[✓] SentenceTransformer embedding model ready")

        api_key = config.GROQ_API_KEY
        if not api_key:
            print("[ERROR] GROQ_API_KEY is not set. Set it as an environment variable.")
            sys.exit(1)
        groq_client = Groq(api_key=api_key)

        retriever = HybridRetriever(
            chunk_store=chunk_store,
            embedder=embedder,
            graph=graph,
            debug_logger=log_retrieval,
        )

        print("[✓] RAG engine ready (hybrid vector + graph retrieval)\n")
        return cls(chunk_store, retriever, groq_client)

    def retrieve(self, question: str, history: list[dict]) -> list[str]:
        return self.retriever.retrieve(question, history)

    def answer(self, question: str, context_chunks: list[str], history: list[dict]) -> str:
        return ask_groq(self.groq_client, question, context_chunks, history)

    def parse(self, question: str, history: list[dict]) -> dict:
        return parse_query(question, history)
