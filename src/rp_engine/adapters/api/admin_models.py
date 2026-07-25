from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from rp_engine.application.services.admin_service import AdminUserSummary
from rp_engine.core.conversation.message import ConversationMessage
from rp_engine.core.scenario.scenario_session import ScenarioSession


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


class AdminSessionResponse(BaseModel):
    id: UUID
    scenario_definition_id: str
    owner_kind: str
    owner_id: UUID
    created_at: datetime
    message_count: int | None = None

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
            message_count=message_count,
        )


class AdminMessageResponse(BaseModel):
    role: str
    content: str
    metadata: dict[str, str]

    @classmethod
    def from_message(cls, message: ConversationMessage) -> "AdminMessageResponse":
        return cls(role=message.role.value, content=message.content, metadata=message.metadata)


class AdminTraceResponse(BaseModel):
    record: dict[str, object]
