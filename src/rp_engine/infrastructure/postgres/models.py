from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Index, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class ConversationMessageRecord(Base):
    __tablename__ = "conversation_messages"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    memory_key: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    session_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), nullable=True, index=True)
    role: Mapped[str] = mapped_column(String(32), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    payload_metadata: Mapped[dict[str, object]] = mapped_column(
        "metadata",
        JSONB,
        nullable=False,
        default=dict,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    __table_args__ = (Index("ix_conversation_messages_memory_order", "memory_key", "created_at"),)


class ScenarioDefinitionRecord(Base):
    __tablename__ = "scenario_definitions"

    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    owner_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    world: Mapped[dict[str, object] | None] = mapped_column(JSONB, nullable=True)
    characters: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False, default=dict)
    rules: Mapped[list[object]] = mapped_column(JSONB, nullable=False, default=list)
    story_graph: Mapped[dict[str, object] | None] = mapped_column(JSONB, nullable=True)
    initial_context: Mapped[str] = mapped_column(Text, nullable=False, default="")
    visibility: Mapped[str] = mapped_column(String(16), nullable=False, default="PUBLIC")
    allowed_group_chat_ids: Mapped[list[object]] = mapped_column(
        JSONB, nullable=False, default=list
    )
    payload_metadata: Mapped[dict[str, object]] = mapped_column(
        "metadata",
        JSONB,
        nullable=False,
        default=dict,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class ScenarioSessionRecord(Base):
    __tablename__ = "scenario_sessions"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    scenario_definition_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    owner_kind: Mapped[str] = mapped_column(String(16), nullable=False)
    owner_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    active_participants: Mapped[dict[str, object]] = mapped_column(
        JSONB, nullable=False, default=dict
    )
    world_state: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False, default=dict)
    story_progress: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    payload_metadata: Mapped[dict[str, object]] = mapped_column(
        "metadata",
        JSONB,
        nullable=False,
        default=dict,
    )

    __table_args__ = (
        Index(
            "ix_scenario_sessions_owner_definition",
            "owner_kind",
            "owner_id",
            "scenario_definition_id",
        ),
    )


class ActiveScenarioSessionRecord(Base):
    __tablename__ = "active_scenario_sessions"

    owner_kind: Mapped[str] = mapped_column(String(16), primary_key=True)
    owner_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    session_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("scenario_sessions.id", ondelete="CASCADE"),
        nullable=False,
    )
