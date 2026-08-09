"""
rag_engine.auth
────────────────
JWT authentication utilities and Flask route decorator.
"""
import datetime
import functools

import bcrypt
import jwt
from flask import request, jsonify, g

from . import config
from .database import get_session
from .models import User


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))


def create_token(user_id: str) -> str:
    payload = {
        "sub": user_id,
        "iat": datetime.datetime.now(datetime.timezone.utc),
        "exp": datetime.datetime.now(datetime.timezone.utc)
              + datetime.timedelta(hours=config.JWT_EXPIRY_HOURS),
    }
    return jwt.encode(payload, config.JWT_SECRET_KEY, algorithm="HS256")


def decode_token(token: str) -> str:
    """Returns user_id or raises jwt.InvalidTokenError."""
    payload = jwt.decode(token, config.JWT_SECRET_KEY, algorithms=["HS256"])
    return payload["sub"]


def require_auth(f):
    """Flask route decorator — sets g.current_user_id on success."""
    @functools.wraps(f)
    def wrapper(*args, **kwargs):
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return jsonify({"error": "Missing or invalid Authorization header"}), 401
        token = auth_header[7:]
        try:
            user_id = decode_token(token)
        except jwt.ExpiredSignatureError:
            return jsonify({"error": "Token expired"}), 401
        except jwt.InvalidTokenError:
            return jsonify({"error": "Invalid token"}), 401
        # Verify user still exists
        with get_session() as session:
            user = session.query(User).filter_by(id=user_id).first()
            if not user:
                return jsonify({"error": "User not found"}), 401
        g.current_user_id = user_id
        return f(*args, **kwargs)
    return wrapper
