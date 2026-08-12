"""
rag_engine.database
─────────────────────
SQLAlchemy engine + session factory for PostgreSQL with pgvector.
"""
import os
from contextlib import contextmanager
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, DeclarativeBase

from . import config


class Base(DeclarativeBase):
    pass


_engine = None
_SessionLocal = None


def get_engine():
    global _engine
    if _engine is None:
        _engine = create_engine(
            config.DATABASE_URL,
            pool_size=5,
            max_overflow=10,
            pool_pre_ping=True,
        )
    return _engine


def get_session_factory():
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(bind=get_engine(), expire_on_commit=False)
    return _SessionLocal


@contextmanager
def get_session():
    """Context manager that yields a session and handles commit/rollback."""
    Session = get_session_factory()
    session = Session()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def create_tables():
    """Create all tables and enable pgvector extension (fail-safe)."""
    try:
        engine = get_engine()
        with engine.connect() as conn:
            try:
                conn.execute(text('CREATE EXTENSION IF NOT EXISTS vector'))
                conn.commit()
            except Exception as e:
                conn.rollback()
                print(f"[WARN] Could not create pgvector extension: {e}")
        from . import models  # noqa: F401 — registers models with Base
        Base.metadata.create_all(engine)
        print("[✓] Database tables ready")
    except Exception as e:
        print(f"[ERROR] Failed to initialize database tables: {e}")
