from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import UUID, uuid4


@dataclass(frozen=True, slots=True)
class Session:
    id: UUID
    user_id: UUID
    character_id: str
    world_id: str
    created_at: datetime
    metadata: dict[str, str] = field(default_factory=dict)

    @classmethod
    def create(
        cls,
        *,
        user_id: UUID,
        character_id: str,
        world_id: str,
        metadata: dict[str, str] | None = None,
    ) -> "Session":
        return cls(
            id=uuid4(),
            user_id=user_id,
            character_id=character_id,
            world_id=world_id,
            created_at=datetime.now(UTC),
            metadata=metadata or {},
        )
