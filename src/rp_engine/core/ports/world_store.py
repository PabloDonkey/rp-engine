from typing import Protocol

from rp_engine.core.world.world import World


class WorldStore(Protocol):
    async def get_by_id(self, world_id: str) -> World | None: ...

    async def create_default(self, *, world_id: str) -> World: ...
