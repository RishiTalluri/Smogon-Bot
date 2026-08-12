"""
Smogon RAG Bot — Flask Backend
Wraps rag_engine (hybrid vector + graph retrieval) behind a REST API.
Now using PostgreSQL for persistence and Authentication.
"""

import os
import time
import uuid
from flask import Flask, request, jsonify, g, send_from_directory
from flask_cors import CORS

from rag_engine.engine import RagEngine
from rag_engine.database import get_session, create_tables
from rag_engine.models import User, Chat, Message
from rag_engine.auth import hash_password, verify_password, create_token, require_auth

app = Flask(__name__)
app.url_map.strict_slashes = False
# CORS: allow all origins, methods, and headers for Vercel frontend
CORS(app, resources={r"/*": {"origins": "*"}}, allow_headers="*", methods="*")

# ── Boot DB (once at startup) ──────────────────────────────────────────────────
print("[*] Creating database tables...")
create_tables()

# ── Lazy-load RAG engine (on first request, not at import time) ────────────────
# This lets gunicorn bind the port instantly so Render's health check passes,
# while the heavy ML model loads on the first actual query.
_engine = None

def get_engine():
    global _engine
    if _engine is None:
        print("[*] Booting RAG engine (first request)…")
        _engine = RagEngine.load()
    return _engine

# ── Static Frontend Serving (only when built frontend exists, e.g. Docker) ────
STATIC_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'static')

if os.path.isdir(STATIC_DIR):
    @app.route('/', defaults={'path': ''})
    @app.route('/<path:path>')
    def serve_frontend(path):
        if path and os.path.exists(os.path.join(STATIC_DIR, path)):
            return send_from_directory(STATIC_DIR, path)
        return send_from_directory(STATIC_DIR, 'index.html')

# ── Helpers ───────────────────────────────────────────────────────────────────
def build_rag_history(messages):
    """Convert DB messages into the format RagEngine expects."""
    history = []
    i = 0
    while i < len(messages) - 1:
        if messages[i].role == 'user' and messages[i+1].role == 'assistant':
            parsed = {}
            if messages[i+1].metadata_json:
                parsed = messages[i+1].metadata_json.get('parsed', {})
            history.append({
                'user': messages[i].content,
                'bot': messages[i+1].content,
                'parsed': parsed,
            })
            i += 2
        else:
            i += 1
    return history

from werkzeug.exceptions import HTTPException

@app.errorhandler(Exception)
def handle_exception(e):
    if isinstance(e, HTTPException):
        return e
    import traceback
    traceback.print_exc()
    return jsonify({"error": str(e)}), 500


@app.route("/", methods=["GET", "HEAD"])
def index():
    return jsonify({"message": "Smogon Bot API is running", "health": "/api/health"})


@app.route("/api/health", methods=["GET"])
def health():
    from rag_engine import config
    return jsonify({"status": "ok", "model": config.GROQ_MODEL})


@app.route("/api/auth/register", methods=["POST"])
def register():
    body = request.get_json(silent=True) or {}
    username = body.get("username", "").strip()
    email = body.get("email", "").strip()
    password = body.get("password", "")

    if len(username) < 3:
        return jsonify({"error": "username must be at least 3 characters"}), 400
    if "@" not in email:
        return jsonify({"error": "invalid email"}), 400
    if len(password) < 6:
        return jsonify({"error": "password must be at least 6 characters"}), 400

    with get_session() as session:
        # Check uniqueness
        existing_user = session.query(User).filter((User.username == username) | (User.email == email)).first()
        if existing_user:
            return jsonify({"error": "username or email already exists"}), 409
        
        user = User(
            id=str(uuid.uuid4()),
            username=username,
            email=email,
            password_hash=hash_password(password)
        )
        session.add(user)
        user_id, u_name, u_email = user.id, user.username, user.email

    token = create_token(user_id)
    return jsonify({
        "token": token,
        "user": {"id": user_id, "username": u_name, "email": u_email}
    }), 201


@app.route("/api/auth/login", methods=["POST"])
def login():
    body = request.get_json(silent=True) or {}
    email = body.get("email", "").strip()
    password = body.get("password", "")

    with get_session() as session:
        user = session.query(User).filter(User.email == email).first()
        if not user or not verify_password(password, user.password_hash):
            return jsonify({"error": "Invalid email or password"}), 401

        token = create_token(user.id)
        return jsonify({
            "token": token,
            "user": {"id": user.id, "username": user.username, "email": user.email}
        })


@app.route("/api/auth/me", methods=["GET"])
@require_auth
def get_me():
    with get_session() as session:
        user = session.query(User).filter(User.id == g.current_user_id).first()
        if not user:
            return jsonify({"error": "User not found"}), 404
        return jsonify({
            "id": user.id,
            "username": user.username,
            "email": user.email
        })


# ── Chat Routes ───────────────────────────────────────────────────────────────

@app.route("/api/chats", methods=["GET"])
@require_auth
def list_chats():
    """Return all chats sorted newest-first."""
    with get_session() as session:
        chats = session.query(Chat).filter(Chat.user_id == g.current_user_id).order_by(Chat.created_at.desc()).all()
        summaries = []
        for chat in chats:
            summaries.append({
                "id": chat.id,
                "title": chat.title,
                "created_at": chat.created_at.timestamp() if chat.created_at else time.time(),
                "msg_count": len(chat.messages)
            })
        return jsonify(summaries)


@app.route("/api/chats", methods=["POST"])
@require_auth
def create_chat():
    """Create a new empty chat."""
    with get_session() as session:
        chat = Chat(
            id=str(uuid.uuid4()),
            user_id=g.current_user_id,
            title="New Chat"
        )
        session.add(chat)
        return jsonify({
            "id": chat.id,
            "title": chat.title,
            "created_at": chat.created_at.timestamp() if chat.created_at else time.time(),
            "msg_count": 0
        }), 201


@app.route("/api/chats/<chat_id>", methods=["GET"])
@require_auth
def get_chat(chat_id):
    """Return full message history for a chat."""
    with get_session() as session:
        chat = session.query(Chat).filter(Chat.id == chat_id, Chat.user_id == g.current_user_id).first()
        if not chat:
            return jsonify({"error": "Chat not found"}), 404
        
        history = [{"role": msg.role, "content": msg.content} for msg in chat.messages]
        
        return jsonify({
            "id": chat.id,
            "title": chat.title,
            "history": history,
            "raw_history": build_rag_history(chat.messages),
        })


@app.route("/api/chats/<chat_id>", methods=["DELETE"])
@require_auth
def delete_chat(chat_id):
    """Delete a chat."""
    with get_session() as session:
        chat = session.query(Chat).filter(Chat.id == chat_id, Chat.user_id == g.current_user_id).first()
        if not chat:
            return jsonify({"error": "Chat not found"}), 404
        
        session.delete(chat)
        return jsonify({"deleted": chat_id})


@app.route("/api/chats/<chat_id>/messages", methods=["POST"])
@require_auth
def send_message(chat_id):
    """
    Send a user message to a chat.
    Body: { "message": "..." }
    """
    body = request.get_json(silent=True) or {}
    question = (body.get("message") or "").strip()
    if not question:
        return jsonify({"error": "message is required"}), 400

    with get_session() as session:
        chat = session.query(Chat).filter(Chat.id == chat_id, Chat.user_id == g.current_user_id).first()
        if not chat:
            return jsonify({"error": "Chat not found"}), 404

        messages = chat.messages
        history = build_rag_history(messages)

        if not messages:
            chat.title = question[:48] + ("…" if len(question) > 48 else "")
            session.add(chat)

        try:
            relevant_chunks = get_engine().retrieve(question, history)

            if not relevant_chunks:
                answer = (
                    "I couldn't find relevant data for that. "
                    "Try being more specific — e.g. *'Gholdengo SV OU moveset'* "
                    "or *'why was Iron Bundle banned SV OU'*."
                )
                chunks_used = 0
            else:
                answer = get_engine().answer(question, relevant_chunks, history)
                chunks_used = len(relevant_chunks)

            parsed = get_engine().parse(question, history)

            # Store User Message
            user_msg = Message(
                chat_id=chat.id,
                role="user",
                content=question,
                metadata_json=None
            )
            session.add(user_msg)
            
            # Store Bot Message
            bot_msg = Message(
                chat_id=chat.id,
                role="assistant",
                content=answer,
                metadata_json={"parsed": parsed, "chunks_used": chunks_used}
            )
            session.add(bot_msg)

            return jsonify({
                "answer": answer,
                "chunks_used": chunks_used,
                "corrected_mon": parsed.get("mon") or None,
            })

        except Exception as e:
            return jsonify({"error": str(e)}), 500


@app.route("/api/chats/<chat_id>/clear", methods=["POST"])
@require_auth
def clear_chat(chat_id):
    """Clear history but keep the chat."""
    with get_session() as session:
        chat = session.query(Chat).filter(Chat.id == chat_id, Chat.user_id == g.current_user_id).first()
        if not chat:
            return jsonify({"error": "Chat not found"}), 404
        
        session.query(Message).filter(Message.chat_id == chat.id).delete()
        chat.title = "New Chat"
        
        return jsonify({"cleared": chat_id})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
