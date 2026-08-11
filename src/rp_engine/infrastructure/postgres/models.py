from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, func, text
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
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    # Null means "this is the live session for its owner + scenario". Set when a reset
    # (`/restart`, `/clear`) supersedes it; the row and its transcript stay readable by id.
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    payload_metadata: Mapped[dict[str, object]] = mapped_column(
        "metadata",
        JSONB,
        nullable=False,
        default=dict,
    )
    directives: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False, default=dict)
    user_persona_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    user_persona_description: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        # Partial *and unique*: every hot lookup asks for the owner's live session, so
        # superseded rows are dead weight in the index — and "one live session per owner
        # per scenario" is the invariant the engine has always assumed. Enforcing it here
        # is what stops a duplicate from silently turning `find_by_definition` into a
        # coin flip between the current story and a retired one.
        Index(
            "ix_scenario_sessions_owner_definition",
            "owner_kind",
            "owner_id",
            "scenario_definition_id",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
    )


class SessionSummaryRecord(Base):
    """Layer 01's running recap, one row per session (ADR-026, S023).

    `covers_through_turn` is the load-bearing column: it is what the background worker
    re-reads to answer "is this session's recap behind?", and it is why the job that wakes
    the worker can carry a session id instead of a list of messages.
    """

    __tablename__ = "session_summaries"

    session_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("scenario_sessions.id", ondelete="CASCADE"),
        primary_key=True,
    )
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    covers_through_turn: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # Which model wrote it. The token count beside it was made with that model's tokenizer,
    # so a model swap is visible here rather than hidden in a stale number.
    model_name: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ActiveScenarioSessionRecord(Base):
    __tablename__ = "active_scenario_sessions"

    owner_kind: Mapped[str] = mapped_column(String(16), primary_key=True)
    owner_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    session_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("scenario_sessions.id", ondelete="CASCADE"),
        nullable=False,
    )


class UserRecord(Base):
    __tablename__ = "users"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)


class UserIdentityRecord(Base):
    __tablename__ = "user_identities"

    provider: Mapped[str] = mapped_column(String(64), primary_key=True)
    external_id: Mapped[str] = mapped_column(String(255), primary_key=True)
    user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    identity_metadata: Mapped[dict[str, str]] = mapped_column(
        "metadata",
        JSONB,
        nullable=False,
        default=dict,
    )


class GroupRecord(Base):
    __tablename__ = "groups"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)


class GroupIdentityRecord(Base):
    __tablename__ = "group_identities"

    provider: Mapped[str] = mapped_column(String(64), primary_key=True)
    external_id: Mapped[str] = mapped_column(String(255), primary_key=True)
    group_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("groups.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    identity_metadata: Mapped[dict[str, str]] = mapped_column(
        "metadata",
        JSONB,
        nullable=False,
        default=dict,
    )


class GenerationTraceRecord(Base):
    __tablename__ = "generation_traces"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    # No index=True here: the composite index below already covers session_id lookups via
    # its leftmost column, so a standalone index would just be redundant.
    session_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    record: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    __table_args__ = (Index("ix_generation_traces_session_created", "session_id", "created_at"),)
