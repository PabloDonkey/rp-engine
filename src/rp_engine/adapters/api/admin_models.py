from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from rp_engine.application.services.admin_service import AdminDeletedMessage, AdminUserSummary
from rp_engine.core.conversation.message import ConversationMessage
from rp_engine.core.scenario.scenario_definition import ScenarioDefinition
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
    director_instruction: str

    @classmethod
    def from_directives(cls, directives: SessionDirectives) -> "AdminSessionDirectivesResponse":
        return cls(
            language=directives.language,
            rules=[
                AdminScenarioRuleResponse(id=rule.id, text=rule.text) for rule in directives.rules
            ],
            director_instruction=directives.director_instruction,
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
            user_persona_name=session.user_persona_name,
            user_persona_description=session.user_persona_description,
        )


class AdminMessageResponse(BaseModel):
    role: str
    content: str
    metadata: dict[str, str]

    @classmethod
    def from_message(cls, message: ConversationMessage) -> "AdminMessageResponse":
        return cls(role=message.role.value, content=message.content, metadata=message.metadata)


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


class ScenarioSummaryResponse(BaseModel):
    id: str
    name: str
    description: str
    visibility: str

    @classmethod
    def from_definition(cls, scenario: ScenarioDefinition) -> "ScenarioSummaryResponse":
        return cls(
            id=scenario.id,
            name=scenario.name,
            description=scenario.description,
            visibility=scenario.visibility.value,
        )
