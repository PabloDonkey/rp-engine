from dataclasses import dataclass
from typing import Literal

MemoryOwnerKind = Literal["user", "group", "session"]


@dataclass(frozen=True, slots=True)
class MemoryKey:
    value: str


@dataclass(frozen=True, slots=True)
class ConversationIdentity:
    owner_kind: MemoryOwnerKind
    owner_id: str

    @classmethod
    def for_private(cls, user_id: str) -> "ConversationIdentity":
        return cls(owner_kind="user", owner_id=user_id)

    @classmethod
    def for_group(cls, group_id: str) -> "ConversationIdentity":
        return cls(owner_kind="group", owner_id=group_id)

    @classmethod
    def for_session(cls, session_id: str) -> "ConversationIdentity":
        return cls(owner_kind="session", owner_id=session_id)

    def to_memory_key(self) -> MemoryKey:
        if self.owner_kind == "user":
            prefix = "user"
        elif self.owner_kind == "group":
            prefix = "group"
        else:
            prefix = "session"
        return MemoryKey(value=f"{prefix}_{self.owner_id}")
