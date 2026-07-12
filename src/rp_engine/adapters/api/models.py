from typing import Literal

from pydantic import BaseModel, Field, field_validator

from rp_engine.core.memory.models import ConversationIdentity


class IdentityPayload(BaseModel):
    owner_kind: Literal["session"]
    owner_id: str = Field(min_length=1)

    @field_validator("owner_id")
    @classmethod
    def validate_owner_id(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("owner_id must not be empty")
        return cleaned

    def to_identity(self) -> ConversationIdentity:
        return ConversationIdentity.for_session(self.owner_id)


class ChatRequest(IdentityPayload):
    message: str = Field(min_length=1)

    @field_validator("message")
    @classmethod
    def validate_message(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("message must not be empty")
        return cleaned


class ContinueRequest(IdentityPayload):
    pass


class ClearConversationRequest(IdentityPayload):
    pass
