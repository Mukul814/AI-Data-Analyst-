import uuid
from datetime import UTC, datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


def now():
    return datetime.now(UTC)


class Project(Base):
    __tablename__ = "projects"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    datasets: Mapped[list["Dataset"]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )


class Dataset(Base):
    __tablename__ = "datasets"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    storage_key: Mapped[str] = mapped_column(String(512), nullable=False)
    profile: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    project: Mapped[Project] = relationship(back_populates="datasets")
    conversations: Mapped[list["Conversation"]] = relationship(
        back_populates="dataset", cascade="all, delete-orphan"
    )
    dataset_columns: Mapped[list["DatasetColumn"]] = relationship(
        back_populates="dataset", cascade="all, delete-orphan"
    )


class DatasetColumn(Base):
    __tablename__ = "dataset_columns"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    dataset_id: Mapped[str] = mapped_column(
        ForeignKey("datasets.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    dtype: Mapped[str] = mapped_column(String(80), nullable=False)
    semantic_type: Mapped[str] = mapped_column(String(40), nullable=False)
    details: Mapped[dict] = mapped_column(JSON, nullable=False)
    dataset: Mapped[Dataset] = relationship(back_populates="dataset_columns")


class Conversation(Base):
    __tablename__ = "conversations"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    dataset_id: Mapped[str] = mapped_column(
        ForeignKey("datasets.id", ondelete="CASCADE"), index=True
    )
    title: Mapped[str] = mapped_column(String(255), default="New analysis")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    dataset: Mapped[Dataset] = relationship(back_populates="conversations")
    messages: Mapped[list["Message"]] = relationship(
        back_populates="conversation", cascade="all, delete-orphan"
    )


class Message(Base):
    __tablename__ = "messages"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    conversation_id: Mapped[str] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"), index=True
    )
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    conversation: Mapped[Conversation] = relationship(back_populates="messages")


class AnalysisSession(Base):
    __tablename__ = "analysis_sessions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    conversation_id: Mapped[str] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"), index=True
    )
    status: Mapped[str] = mapped_column(String(24), default="completed")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    result: Mapped["AnalysisResult"] = relationship(
        back_populates="session", cascade="all, delete-orphan", uselist=False
    )


class AnalysisResult(Base):
    __tablename__ = "analysis_results"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id: Mapped[str] = mapped_column(
        ForeignKey("analysis_sessions.id", ondelete="CASCADE"), unique=True
    )
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    code: Mapped[str | None] = mapped_column(Text)
    session: Mapped[AnalysisSession] = relationship(back_populates="result")


Index("ix_messages_conversation_created", Message.conversation_id, Message.created_at)
