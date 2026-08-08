"""
Smogon RAG Bot — Terminal CLI
Thin wrapper around rag_engine (hybrid vector + graph retrieval + Groq).
Run: python Bot.py
"""

import sys

from rag_engine import config
from rag_engine.engine import RagEngine


def main():
    engine = RagEngine.load()
    history: list[dict] = []

    print("=" * 60)
    print("  Smogon RAG Bot  |  'quit' to exit | 'debug' to toggle | 'clear' to reset history")
    print("=" * 60)

    while True:
        try:
            question = input("\nYou: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n[Bye!]")
            break

        if not question:
            continue
        if question.lower() in {"quit", "exit", "q"}:
            print("[Bye!]")
            break
        if question.lower() == "debug":
            config.SHOW_RETRIEVAL_DEBUG = not config.SHOW_RETRIEVAL_DEBUG
            print(f"[Retrieval debug: {'ON' if config.SHOW_RETRIEVAL_DEBUG else 'OFF'}]")
            continue
        if question.lower() == "clear":
            history.clear()
            print("[Conversation history cleared]")
            continue

        print("[*] Retrieving (hybrid vector + graph)...")
        relevant_chunks = engine.retrieve(question, history)

        if not relevant_chunks:
            print("Bot: No relevant chunks found.")
            print("     Tip: Be specific — e.g. 'Gholdengo SV OU moveset' or 'why was X banned from SV OU'")
            continue

        print(f"[*] Sending {len(relevant_chunks)} chunks to LLM ({config.GROQ_MODEL})...\n")
        try:
            answer = engine.answer(question, relevant_chunks, history)
            print(f"Bot: {answer}")

            parsed = engine.parse(question, history)
            history.append({"user": question, "bot": answer, "parsed": parsed})

        except Exception as e:
            print(f"[ERROR] {e}")


if __name__ == "__main__":
    main()
