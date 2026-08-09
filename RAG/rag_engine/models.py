"""
rag_engine.models
───────────────────
SQLAlchemy ORM models for the Smogon RAG Bot.
"""
import datetime
import uuid

from sqlalchemy import (
    Column, Integer, String, Text, Boolean, Float,
    DateTime, ForeignKey, Index,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import relationship
from pgvector.sqlalchemy import Vector

from .database import Base


def _uuid():
    return str(uuid.uuid4())


def _now():
    return datetime.datetime.now(datetime.timezone.utc)


class User(Base):
    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=_uuid)
    username = Column(String(50), unique=True, nullable=False)
    email = Column(String(255), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    created_at = Column(DateTime(timezone=True), default=_now)

    chats = relationship("Chat", back_populates="user", cascade="all, delete-orphan")


class Chat(Base):
    __tablename__ = "chats"

    id = Column(String(36), primary_key=True, default=_uuid)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    title = Column(String(255), default="New Chat")
    created_at = Column(DateTime(timezone=True), default=_now)

    user = relationship("User", back_populates="chats")
    messages = relationship(
        "Message", back_populates="chat",
        cascade="all, delete-orphan",
        order_by="Message.created_at",
    )


class Message(Base):
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    chat_id = Column(String(36), ForeignKey("chats.id", ondelete="CASCADE"), nullable=False)
    role = Column(String(20), nullable=False)  # 'user' or 'assistant'
    content = Column(Text, nullable=False)
    metadata_json = Column(JSONB, nullable=True)
    created_at = Column(DateTime(timezone=True), default=_now)

    chat = relationship("Chat", back_populates="messages")


class Chunk(Base):
    __tablename__ = "chunks"

    id = Column(Integer, primary_key=True)
    text = Column(Text, nullable=False)
    content = Column(Text)
    title = Column(String(500))
    forum = Column(String(255))
    url = Column(Text)
    is_team = Column(Boolean, default=False)
    source = Column(String(100))
    mons = Column(ARRAY(String))
    tiers = Column(ARRAY(String))
    gen_tag = Column(String(10))
    embedding = Column(Vector(384))

    __table_args__ = (
        Index("ix_chunks_mons", mons, postgresql_using="gin"),
        Index("ix_chunks_tiers", tiers, postgresql_using="gin"),
    )


class GraphEdge(Base):
    __tablename__ = "graph_edges"

    id = Column(Integer, primary_key=True, autoincrement=True)
    source_node = Column(String(255), nullable=False, index=True)
    target_node = Column(String(255), nullable=False, index=True)
    kind = Column(String(50), nullable=False)
    weight = Column(Float, default=1.0)

    __table_args__ = (
        Index("ix_graph_edges_source_kind", source_node, kind),
        Index("ix_graph_edges_target_kind", target_node, kind),
    )
