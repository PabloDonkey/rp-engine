from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from rp_engine.core.group.group import Group
from rp_engine.core.group.identity import GroupIdentity
from rp_engine.core.ports.group_identity_store import GroupIdentityStore
from rp_engine.infrastructure.postgres.models import GroupIdentityRecord, GroupRecord
from rp_engine.infrastructure.postgres.transaction import session_scope


class PostgresGroupIdentityStore(GroupIdentityStore):
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def get_by_id(self, group_id: UUID) -> Group | None:
        async with self._session_factory() as db_session:
            group_record = await db_session.get(GroupRecord, group_id)
            if group_record is None:
                return None
            identities = await self._load_identities(db_session, group_id)
            return self._to_domain(group_record, identities)

    async def get_group_by_identity(self, *, provider: str, external_id: str) -> Group | None:
        statement = select(GroupIdentityRecord).where(
            GroupIdentityRecord.provider == provider,
            GroupIdentityRecord.external_id == external_id,
        )
        async with self._session_factory() as db_session:
            identity_record = await db_session.scalar(statement)
        if identity_record is None:
            return None
        return await self.get_by_id(identity_record.group_id)

    async def create_group_with_identity(
        self,
        *,
        display_name: str,
        identity: GroupIdentity,
    ) -> Group:
        existing = await self.get_group_by_identity(
            provider=identity.provider, external_id=identity.external_id
        )
        if existing is not None:
            return existing

        group = Group.create(display_name=display_name, identities=(identity,))
        try:
            async with session_scope(self._session_factory) as db_session:
                db_session.add(GroupRecord(id=group.id, display_name=group.display_name))
                # No ORM relationship links GroupRecord/GroupIdentityRecord, so flush order
                # isn't otherwise guaranteed; the identity row's FK needs the group committed first.
                await db_session.flush()
                db_session.add(
                    GroupIdentityRecord(
                        provider=identity.provider,
                        external_id=identity.external_id,
                        group_id=group.id,
                        identity_metadata=dict(identity.metadata),
                    )
                )
        except IntegrityError:
            raced = await self.get_group_by_identity(
                provider=identity.provider, external_id=identity.external_id
            )
            if raced is not None:
                return raced
            raise
        return group

    async def _load_identities(
        self, db_session: AsyncSession, group_id: UUID
    ) -> list[GroupIdentityRecord]:
        statement = select(GroupIdentityRecord).where(GroupIdentityRecord.group_id == group_id)
        return list((await db_session.scalars(statement)).all())

    @staticmethod
    def _to_domain(group_record: GroupRecord, identities: list[GroupIdentityRecord]) -> Group:
        return Group(
            id=group_record.id,
            display_name=group_record.display_name,
            identities=tuple(
                GroupIdentity(
                    provider=record.provider,
                    external_id=record.external_id,
                    metadata=dict(record.identity_metadata),
                )
                for record in identities
            ),
        )
