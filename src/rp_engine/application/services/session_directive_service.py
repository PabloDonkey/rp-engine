import logging
from uuid import UUID

from rp_engine.core.ports.scenario_session_store import ScenarioSessionStore
from rp_engine.core.scenario.scenario_session import ScenarioSession
from rp_engine.core.scenario.session_directives import (
    ScenarioRule,
    SessionDirectives,
)

logger = logging.getLogger(__name__)


class SessionDirectiveService:
    """Read/write the player directives attached to a scenario session.

    The directives themselves are domain logic (`SessionDirectives` owns validation and
    rule-id allocation); this service only decides *when* they are persisted, so adapters
    never touch `ScenarioSessionStore` directly.
    """

    def __init__(self, *, scenario_session_store: ScenarioSessionStore) -> None:
        self._scenario_session_store = scenario_session_store

    async def get(self, *, session_id: UUID) -> SessionDirectives | None:
        session = await self._scenario_session_store.get_by_id(session_id)
        if session is None:
            return None
        return session.directives

    async def set_language(
        self,
        *,
        session: ScenarioSession,
        language: str,
    ) -> SessionDirectives:
        """Set the persistent language preference. Raises ValueError on an unknown code."""
        updated = session.directives.with_language(language)
        await self._save(session, updated)
        logger.info(
            "Session language set",
            extra={"session_id": str(session.id), "language": updated.language},
        )
        return updated

    async def add_rule(self, *, session: ScenarioSession, text: str) -> ScenarioRule:
        """Append a persistent scenario rule. Raises ValueError on empty text."""
        updated, rule = session.directives.with_rule(text)
        await self._save(session, updated)
        logger.info(
            "Session rule added",
            extra={"session_id": str(session.id), "rule_id": rule.id},
        )
        return rule

    async def remove_rule(self, *, session: ScenarioSession, rule_id: str) -> bool:
        """Remove a rule by id; False when the session has no rule with that id."""
        updated = session.directives.without_rule(rule_id)
        if updated is None:
            return False
        await self._save(session, updated)
        logger.info(
            "Session rule removed",
            extra={"session_id": str(session.id), "rule_id": rule_id},
        )
        return True

    async def set_director_instruction(
        self,
        *,
        session: ScenarioSession,
        instruction: str,
    ) -> SessionDirectives:
        """Arm a one-turn director instruction. The next successful generation consumes
        and clears it (see `ChatService`). Raises ValueError on empty text."""
        updated = session.directives.with_director_instruction(instruction)
        await self._save(session, updated)
        logger.info("Director instruction set", extra={"session_id": str(session.id)})
        return updated

    async def clear_director_instruction(
        self,
        *,
        session: ScenarioSession,
    ) -> SessionDirectives:
        updated = session.directives.without_director_instruction()
        await self._save(session, updated)
        return updated

    async def _save(self, session: ScenarioSession, directives: SessionDirectives) -> None:
        await self._scenario_session_store.save(session.with_directives(directives))
