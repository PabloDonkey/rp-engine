from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from rp_engine.core.ports.user_identity_store import UserIdentityStore
from rp_engine.core.user.identity import UserIdentity
from rp_engine.core.user.user import User
from rp_engine.infrastructure.postgres.models import UserIdentityRecord, UserRecord
from rp_engine.infrastructure.postgres.transaction import session_scope


class PostgresUserIdentityStore(UserIdentityStore):
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def get_by_id(self, user_id: UUID) -> User | None:
        async with self._session_factory() as db_session:
            user_record = await db_session.get(UserRecord, user_id)
            if user_record is None:
                return None
            identities = await self._load_identities(db_session, user_id)
            return self._to_domain(user_record, identities)

    async def list_users(self) -> list[User]:
        async with self._session_factory() as db_session:
            user_records = (await db_session.scalars(select(UserRecord))).all()
            users: list[User] = []
            for user_record in user_records:
                identities = await self._load_identities(db_session, user_record.id)
                users.append(self._to_domain(user_record, identities))
            return users

    async def get_user_by_identity(self, *, provider: str, external_id: str) -> User | None:
        statement = select(UserIdentityRecord).where(
            UserIdentityRecord.provider == provider,
            UserIdentityRecord.external_id == external_id,
        )
        async with self._session_factory() as db_session:
            identity_record = await db_session.scalar(statement)
        if identity_record is None:
            return None
        return await self.get_by_id(identity_record.user_id)

    async def create_user_with_identity(
        self,
        *,
        display_name: str,
        identity: UserIdentity,
    ) -> User:
        existing = await self.get_user_by_identity(
            provider=identity.provider, external_id=identity.external_id
        )
        if existing is not None:
            return existing

        user = User.create(display_name=display_name, identities=(identity,))
        try:
            async with session_scope(self._session_factory) as db_session:
                db_session.add(UserRecord(id=user.id, display_name=user.display_name))
                # No ORM relationship links UserRecord/UserIdentityRecord, so flush order
                # isn't otherwise guaranteed; the identity row's FK needs the user committed first.
                await db_session.flush()
                db_session.add(
                    UserIdentityRecord(
                        provider=identity.provider,
                        external_id=identity.external_id,
                        user_id=user.id,
                        identity_metadata=dict(identity.metadata),
                    )
                )
        except IntegrityError:
            raced = await self.get_user_by_identity(
                provider=identity.provider, external_id=identity.external_id
            )
            if raced is not None:
                return raced
            raise
        return user

    async def _load_identities(
        self, db_session: AsyncSession, user_id: UUID
    ) -> list[UserIdentityRecord]:
        statement = select(UserIdentityRecord).where(UserIdentityRecord.user_id == user_id)
        return list((await db_session.scalars(statement)).all())

    @staticmethod
    def _to_domain(user_record: UserRecord, identities: list[UserIdentityRecord]) -> User:
        return User(
            id=user_record.id,
            display_name=user_record.display_name,
            identities=tuple(
                UserIdentity(
                    provider=record.provider,
                    external_id=record.external_id,
                    metadata=dict(record.identity_metadata),
                )
                for record in identities
            ),
        )
