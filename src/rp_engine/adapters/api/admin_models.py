from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from rp_engine.application.services.admin_service import (
    AdminDeletedMessage,
    AdminScenarioSummary,
    AdminSessionMemory,
    AdminUserSummary,
)
from rp_engine.core.conversation.message import ConversationMessage
from rp_engine.core.memory.fragment import ToggleableMemorySystemId
from rp_engine.core.memory.rolling_summary_source import RollingSummaryStatus
from rp_engine.core.memory.session_summary import SessionSummary
from rp_engine.core.memory.settings import MemorySettings
from rp_engine.core.scenario.lore_entry import LoreEntry, LoreEntryPriority
from rp_engine.core.scenario.scenario_session import ScenarioSession
from rp_engine.core.scenario.session_directives import SessionDirectives


class AdminUserResponse(BaseModel):
    id: UUID
    display_name: str
    telegram_external_id: str | None
    session_count: int
    is_blocked: bool

    @classmethod
    def from_summary(cls, summary: AdminUserSummary, *, is_blocked: bool) -> "AdminUserResponse":
        telegram_id = next(
            (
                identity.external_id
                for identity in summary.user.identities
                if identity.provider == "telegram"
            ),
            None,
        )
        return cls(
            id=summary.user.id,
            display_name=summary.user.display_name,
            telegram_external_id=telegram_id,
            session_count=summary.session_count,
            is_blocked=is_blocked,
        )


class AdminScenarioRuleResponse(BaseModel):
    id: str
    text: str


class AdminSessionDirectivesResponse(BaseModel):
    """The player's directives, read-only: the panel shows what the player set over
    Telegram, it does not author it."""

    language: str
    rules: list[AdminScenarioRuleResponse]
    # Plural since S020: `/director` notes stack until a reply consumes them.
    director_instructions: list[str]

    @classmethod
    def from_directives(cls, directives: SessionDirectives) -> "AdminSessionDirectivesResponse":
        return cls(
            language=directives.language,
            rules=[
                AdminScenarioRuleResponse(id=rule.id, text=rule.text) for rule in directives.rules
            ],
            director_instructions=list(directives.director_instructions),
        )


class AdminSessionMemoryStateResponse(BaseModel):
    """Which memory layers this session runs, and what each may spend.

    The recent conversation is missing on purpose: it is the story itself and cannot be
    switched off, so there is no state to report for it (ADR-026 rule 5).
    """

    enabled_sources: list[str]
    source_budget_shares: dict[str, float]

    @classmethod
    def from_memory(cls, memory: MemorySettings) -> "AdminSessionMemoryStateResponse":
        return cls(
            enabled_sources=list(memory.enabled_sources),
            source_budget_shares={budget.source: budget.share for budget in memory.source_budgets},
        )


class AdminSessionMemoryRequest(BaseModel):
    """Switch one layer on or off. The panel sends one layer at a time, so a failed call
    leaves the other layers exactly as they were."""

    source_id: ToggleableMemorySystemId
    enabled: bool


class AdminMemoryStatusResponse(BaseModel):
    """How close this session is to its next recap, in the worker's own numbers.

    Token totals stop at the window edge: messages older than that are counted, not priced,
    because pricing them means counting the whole history on every read.
    """

    budget_tokens: int
    high_water_tokens: int
    window_tokens: int
    window_messages: int
    stored_messages: int
    turns_total: int
    covers_through_turn: int
    pending_turns: int
    behind_turns: int
    pending_tokens: int
    fold_batch_tokens: int
    summary_tokens: int
    summary_budget_tokens: int
    # Turns the prompt still replays word for word, and whether every stored turn still
    # reaches it. Derived, but the panel should not have to re-derive them.
    verbatim_turns: int
    whole_story_fits: bool
    # 0.0 to 1.0, where 1.0 means the next pass folds. It fills and empties, because the
    # window itself never shrinks when a turn is folded into the recap.
    fold_progress: float

    @classmethod
    def from_status(cls, status: RollingSummaryStatus) -> "AdminMemoryStatusResponse":
        return cls(
            budget_tokens=status.budget_tokens,
            high_water_tokens=status.high_water_tokens,
            window_tokens=status.window_tokens,
            window_messages=status.window_messages,
            stored_messages=status.stored_messages,
            turns_total=status.turns_total,
            covers_through_turn=status.covers_through_turn,
            pending_turns=status.pending_turns,
            behind_turns=status.behind_turns,
            pending_tokens=status.pending_tokens,
            fold_batch_tokens=status.fold_batch_tokens,
            summary_tokens=status.summary_tokens,
            summary_budget_tokens=status.summary_budget_tokens,
            verbatim_turns=status.verbatim_turns,
            whole_story_fits=status.whole_story_fits,
            fold_progress=status.fold_progress,
        )


class AdminSessionSummaryResponse(BaseModel):
    """The recap layer 01 stores, as the model receives it.

    `covers_through_turn` is the number worth reading first: it says how far the recap has
    caught up, and a recap far behind the transcript is the alarm ADR-026 describes.
    """

    summary: str
    covers_through_turn: int
    tokens: int
    model_name: str
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_summary(cls, summary: SessionSummary) -> "AdminSessionSummaryResponse":
        return cls(
            summary=summary.summary,
            covers_through_turn=summary.covers_through_turn,
            tokens=summary.tokens,
            model_name=summary.model_name,
            created_at=summary.created_at,
            updated_at=summary.updated_at,
        )


class AdminSessionMemoryResponse(BaseModel):
    """The whole memory panel for one session, read in one call."""

    settings: AdminSessionMemoryStateResponse
    status: AdminMemoryStatusResponse
    summary: AdminSessionSummaryResponse | None
    # What the pass did, when the panel asked for one. Null on a plain read.
    last_pass: str | None = None

    @classmethod
    def from_memory(cls, memory: AdminSessionMemory) -> "AdminSessionMemoryResponse":
        return cls(
            settings=AdminSessionMemoryStateResponse.from_memory(memory.settings),
            status=AdminMemoryStatusResponse.from_status(memory.status),
            last_pass=memory.last_pass,
            summary=(
                None
                if memory.summary is None
                else AdminSessionSummaryResponse.from_summary(memory.summary)
            ),
        )


class AdminSessionResponse(BaseModel):
    id: UUID
    scenario_definition_id: str
    owner_kind: str
    owner_id: UUID
    created_at: datetime
    updated_at: datetime
    # Set on a session superseded by /restart or /clear. It stays fully readable here —
    # that is the point of superseding rather than deleting.
    deleted_at: datetime | None = None
    message_count: int | None = None
    directives: AdminSessionDirectivesResponse
    memory: AdminSessionMemoryStateResponse
    user_persona_name: str | None = None
    user_persona_description: str | None = None

    @classmethod
    def from_session(
        cls, session: ScenarioSession, *, message_count: int | None = None
    ) -> "AdminSessionResponse":
        return cls(
            id=session.id,
            scenario_definition_id=session.scenario_definition_id,
            owner_kind=session.owner_kind,
            owner_id=session.owner_id,
            created_at=session.created_at,
            updated_at=session.updated_at,
            deleted_at=session.deleted_at,
            message_count=message_count,
            directives=AdminSessionDirectivesResponse.from_directives(session.directives),
            memory=AdminSessionMemoryStateResponse.from_memory(session.memory),
            user_persona_name=session.user_persona_name,
            user_persona_description=session.user_persona_description,
        )


class AdminSessionPersonaRequest(BaseModel):
    """Operator-supplied persona: sets one, or replaces the one already there.

    This is the admin exception to ADR-025's set-once contract. Players still have exactly
    one way to change a persona — `/clear`, which starts a fresh session — because they
    never reach this endpoint.
    """

    name: str
    description: str = ""


class AdminMessageResponse(BaseModel):
    role: str
    content: str
    metadata: dict[str, str]

    @classmethod
    def from_message(cls, message: ConversationMessage) -> "AdminMessageResponse":
        return cls(role=message.role.value, content=message.content, metadata=message.metadata)


class AdminPlayTurnRequest(BaseModel):
    """One turn typed into the panel.

    Mirrors the Telegram path: an empty message is refused before the model is ever asked,
    because a blank turn costs a generation and teaches the story nothing.
    """

    message: str = Field(min_length=1)

    @field_validator("message")
    @classmethod
    def validate_message(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("message must not be empty")
        return cleaned


class AdminDeletedMessageResponse(BaseModel):
    """A delete reports what it removed — traces go with the message they describe."""

    message: AdminMessageResponse
    deleted_traces: int

    @classmethod
    def from_deleted(cls, deleted: AdminDeletedMessage) -> "AdminDeletedMessageResponse":
        return cls(
            message=AdminMessageResponse.from_message(deleted.message),
            deleted_traces=deleted.deleted_traces,
        )


class AdminTraceResponse(BaseModel):
    record: dict[str, object]


class AdminLoreEntryResponse(BaseModel):
    """One lore entry (memory layer 02, ADR-026), as authored in the admin panel."""

    id: str
    scenario_definition_id: str
    title: str
    content: str
    trigger_keys: list[str]
    priority: LoreEntryPriority
    related_entry_ids: list[str]
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_entry(cls, entry: LoreEntry) -> "AdminLoreEntryResponse":
        return cls(
            id=entry.id,
            scenario_definition_id=entry.scenario_definition_id,
            title=entry.title,
            content=entry.content,
            trigger_keys=list(entry.trigger_keys),
            priority=entry.priority,
            related_entry_ids=list(entry.related_entry_ids),
            created_at=entry.created_at,
            updated_at=entry.updated_at,
        )


class AdminLoreEntryCreateRequest(BaseModel):
    """No `id` here: the server generates one. See `AdminService.create_lorebook_entry`."""

    title: str = Field(min_length=1)
    content: str = Field(min_length=1)
    trigger_keys: list[str] = Field(default_factory=list)
    priority: LoreEntryPriority = "normal"
    related_entry_ids: list[str] = Field(default_factory=list)


class AdminLoreEntryUpdateRequest(BaseModel):
    title: str = Field(min_length=1)
    content: str = Field(min_length=1)
    trigger_keys: list[str] = Field(default_factory=list)
    priority: LoreEntryPriority = "normal"
    related_entry_ids: list[str] = Field(default_factory=list)


class ScenarioSummaryResponse(BaseModel):
    id: str
    name: str
    description: str
    visibility: str
    # Live sessions running this scenario. The retire dialog names it before it asks.
    session_count: int
    is_active: bool

    @classmethod
    def from_summary(cls, summary: AdminScenarioSummary) -> "ScenarioSummaryResponse":
        scenario = summary.scenario
        return cls(
            id=scenario.id,
            name=scenario.name,
            description=scenario.description,
            visibility=scenario.visibility.value,
            session_count=summary.session_count,
            is_active=scenario.is_active,
        )
