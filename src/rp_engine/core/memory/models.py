from dataclasses import dataclass
from typing import Literal

MemoryOwnerKind = Literal["session"]


@dataclass(frozen=True, slots=True)
class MemoryKey:
    value: str


@dataclass(frozen=True, slots=True)
class ConversationIdentity:
    owner_kind: MemoryOwnerKind
    owner_id: str

    @classmethod
    def for_session(cls, session_id: str) -> "ConversationIdentity":
        return cls(owner_kind="session", owner_id=session_id)

    def to_memory_key(self) -> MemoryKey:
        return MemoryKey(value=f"session_{self.owner_id}")
