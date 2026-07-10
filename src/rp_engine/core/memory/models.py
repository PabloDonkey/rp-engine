from dataclasses import dataclass
from typing import Literal

Role = Literal["user", "assistant"]
MemoryOwnerKind = Literal["user", "group"]


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

    def to_memory_key(self) -> MemoryKey:
        prefix = "user" if self.owner_kind == "user" else "group"
        return MemoryKey(value=f"{prefix}_{self.owner_id}")


@dataclass(frozen=True, slots=True)
class ConversationMessage:
    role: Role
    content: str
