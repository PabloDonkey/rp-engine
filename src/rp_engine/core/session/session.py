from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Literal
from uuid import UUID, uuid4

SessionOwnerKind = Literal["user", "group"]


@dataclass(frozen=True, slots=True)
class Session:
    id: UUID
    owner_kind: SessionOwnerKind
    owner_id: UUID
    character_id: str
    world_id: str
    created_at: datetime
    metadata: dict[str, str] = field(default_factory=dict)

    @classmethod
    def create_for_user(
        cls,
        *,
        user_id: UUID,
        character_id: str,
        world_id: str,
        metadata: dict[str, str] | None = None,
    ) -> "Session":
        return cls(
            id=uuid4(),
            owner_kind="user",
            owner_id=user_id,
            character_id=character_id,
            world_id=world_id,
            created_at=datetime.now(UTC),
            metadata=metadata or {},
        )

    @classmethod
    def create_for_group(
        cls,
        *,
        group_id: UUID,
        character_id: str,
        world_id: str,
        metadata: dict[str, str] | None = None,
    ) -> "Session":
        return cls(
            id=uuid4(),
            owner_kind="group",
            owner_id=group_id,
            character_id=character_id,
            world_id=world_id,
            created_at=datetime.now(UTC),
            metadata=metadata or {},
        )
