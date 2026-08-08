"""
Smogon RAG Bot — Flask Backend
Wraps rag_engine (hybrid vector + graph retrieval) behind the same REST API
as before. API contract is unchanged — every response still only ever
contains {answer, chunks_used, corrected_mon} (or {error}); nothing about
which chunks were retrieved, their scores, or which retriever found them is
ever sent to a client. That detail is printed to this process's own terminal
only, via rag_engine.debug_logger (see config.SHOW_RETRIEVAL_DEBUG).
Run: python Server.py
"""

import uuid
import time

from flask import Flask, request, jsonify
from flask_cors import CORS

from rag_engine.engine import RagEngine

app = Flask(__name__)
CORS(app)  # allow frontend dev server on any port

# ── Boot RAG (once at startup) ────────────────────────────────────────────────
print("[*] Booting RAG engine…")
engine = RagEngine.load()

# ── In-memory chat store ──────────────────────────────────────────────────────
# { chat_id: { "title": str, "history": [...], "created_at": float } }
chats: dict[str, dict] = {}


def new_chat_obj(title: str = "New Chat") -> dict:
    return {"title": title, "history": [], "created_at": time.time()}


# ── Helpers ───────────────────────────────────────────────────────────────────

def chat_summary(chat_id: str) -> dict:
    c = chats[chat_id]
    last_msg = ""
    if c["history"]:
        last_msg = c["history"][-1]["user"][:60]
    return {
        "id":         chat_id,
        "title":      c["title"],
        "last_msg":   last_msg,
        "created_at": c["created_at"],
        "msg_count":  len(c["history"]),
    }


# ── Routes ────────────────────────────────────────────────────────────────────

@app.route("/api/chats", methods=["GET"])
def list_chats():
    """Return all chats sorted newest-first."""
    summaries = [chat_summary(cid) for cid in chats]
    summaries.sort(key=lambda x: x["created_at"], reverse=True)
    return jsonify(summaries)


@app.route("/api/chats", methods=["POST"])
def create_chat():
    """Create a new empty chat."""
    chat_id = str(uuid.uuid4())
    chats[chat_id] = new_chat_obj()
    return jsonify({"id": chat_id, **chats[chat_id]}), 201


@app.route("/api/chats/<chat_id>", methods=["GET"])
def get_chat(chat_id):
    """Return full message history for a chat."""
    if chat_id not in chats:
        return jsonify({"error": "Chat not found"}), 404
    c = chats[chat_id]
    return jsonify({
        "id":      chat_id,
        "title":   c["title"],
        "history": [{"role": "user", "content": t["user"]} if i % 2 == 0
                    else {"role": "assistant", "content": t["bot"]}
                    for t in c["history"] for i in range(2)],
        "raw_history": c["history"],
    })


@app.route("/api/chats/<chat_id>", methods=["DELETE"])
def delete_chat(chat_id):
    """Delete a chat."""
    if chat_id not in chats:
        return jsonify({"error": "Chat not found"}), 404
    del chats[chat_id]
    return jsonify({"deleted": chat_id})


@app.route("/api/chats/<chat_id>/messages", methods=["POST"])
def send_message(chat_id):
    """
    Send a user message to a chat.
    Body: { "message": "..." }
    Returns: { "answer": "...", "chunks_used": N, "corrected_mon": "..." | null }

    Retrieval internals (which chunks, vector/graph/keyword scores, which
    retriever found each one) are printed to this server's terminal by
    rag_engine.debug_logger — they are never part of this response.
    """
    if chat_id not in chats:
        return jsonify({"error": "Chat not found"}), 404

    body = request.get_json(silent=True) or {}
    question = (body.get("message") or "").strip()
    if not question:
        return jsonify({"error": "message is required"}), 400

    chat = chats[chat_id]
    history = chat["history"]

    if not history:
        chat["title"] = question[:48] + ("…" if len(question) > 48 else "")

    try:
        relevant_chunks = engine.retrieve(question, history)

        if not relevant_chunks:
            answer = (
                "I couldn't find relevant data for that. "
                "Try being more specific — e.g. *'Gholdengo SV OU moveset'* "
                "or *'why was Iron Bundle banned SV OU'*."
            )
            chunks_used = 0
        else:
            answer = engine.answer(question, relevant_chunks, history)
            chunks_used = len(relevant_chunks)

        parsed = engine.parse(question, history)
        history.append({"user": question, "bot": answer, "parsed": parsed})

        return jsonify({
            "answer":        answer,
            "chunks_used":   chunks_used,
            "corrected_mon": parsed.get("mon") or None,
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/chats/<chat_id>/clear", methods=["POST"])
def clear_chat(chat_id):
    """Clear history but keep the chat."""
    if chat_id not in chats:
        return jsonify({"error": "Chat not found"}), 404
    chats[chat_id]["history"] = []
    chats[chat_id]["title"]   = "New Chat"
    return jsonify({"cleared": chat_id})


@app.route("/api/health", methods=["GET"])
def health():
    from rag_engine import config
    return jsonify({"status": "ok", "model": config.GROQ_MODEL})


# ── Entry ─────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
