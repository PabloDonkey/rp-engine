import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast
from unittest.mock import AsyncMock
from uuid import UUID

import pytest
from telegram import Update

from rp_engine.adapters.telegram.adapter import (
    AUTHORIZED_START_NO_PLAY_MESSAGE,
    AUTHORIZED_START_RESUME_MESSAGE,
    CLEAR_CONFIRM_MESSAGE,
    EMPTY_GENERATION_MESSAGE,
    GROUP_ADMIN_ONLY_MESSAGE,
    NO_ACTIVE_PLAYTHROUGH_MESSAGE,
    PERSONA_NAME_REQUIRED_MESSAGE,
    PERSONA_PROMPT_MESSAGE,
    TelegramAdapter,
)
from rp_engine.adapters.telegram.authorization import TelegramAuthorization
from rp_engine.adapters.telegram.beta_registry import TelegramBetaRegistry
from rp_engine.adapters.telegram.commands import build_help_message
from rp_engine.application.services.playthrough_service import PlaythroughStart
from rp_engine.core.group.group import Group
from rp_engine.core.llm.errors import EmptyGenerationError, LLMConnectionError, LLMGenerationError
from rp_engine.core.scenario.scenario_definition import ScenarioDefinition
from rp_engine.core.scenario.scenario_session import ScenarioSession
from rp_engine.core.scenario.session_directives import (
    ScenarioRule,
    SessionDirectives,
)
from rp_engine.core.user.user import User
from rp_engine.infrastructure.scenario_transfer import SYSTEM_OWNER_ID

FIXED_USER_ID = UUID("00000000-0000-0000-0000-000000000042")
FIXED_GROUP_ID = UUID("00000000-0000-0000-0000-000000000555")
FIXED_SESSION_ID = UUID("00000000-0000-0000-0000-000000000099")


def _scenario(
    scenario_id: str, *, name: str, opening: str, description: str = ""
) -> ScenarioDefinition:
    return ScenarioDefinition(
        id=scenario_id,
        owner_id=SYSTEM_OWNER_ID,
        name=name,
        description=description,
        initial_context=opening,
    )


def _session(
    *,
    owner_kind: str = "user",
    owner_id: UUID = FIXED_USER_ID,
    directives: SessionDirectives | None = None,
    user_persona_name: str | None = None,
) -> ScenarioSession:
    return ScenarioSession(
        id=FIXED_SESSION_ID,
        scenario_definition_id="vault",
        owner_kind=owner_kind,  # type: ignore[arg-type]
        owner_id=owner_id,
        active_participants={},
        created_at=datetime(2026, 7, 12, tzinfo=UTC),
        updated_at=datetime(2026, 7, 12, tzinfo=UTC),
        directives=directives or SessionDirectives(),
        user_persona_name=user_persona_name,
    )


class FakeIdentityResolver:
    async def resolve_identity(
        self,
        *,
        provider: str,
        external_id: str,
        display_name: str,
        metadata: dict[str, str] | None = None,
    ) -> User:
        del provider, external_id, metadata
        return User(id=FIXED_USER_ID, display_name=display_name)


class FakeGroupIdentityResolver:
    async def resolve_identity(
        self,
        *,
        provider: str,
        external_id: str,
        display_name: str,
        metadata: dict[str, str] | None = None,
    ) -> Group:
        del provider, external_id, metadata
        return Group(id=FIXED_GROUP_ID, display_name=display_name)


class FakePlaythroughService:
    def __init__(
        self,
        *,
        scenarios: list[ScenarioDefinition] | None = None,
        active: ScenarioSession | None = None,
        known: dict[str, ScenarioDefinition] | None = None,
        resume: str | None = None,
    ) -> None:
        self._scenarios = scenarios or []
        self._active = active
        self._known = known or {}
        self._resume = resume
        self.started: list[tuple[str, UUID, str]] = []
        self.restarted: list[tuple[str, UUID]] = []
        self.cleared: list[tuple[str, UUID]] = []
        self.personas: list[tuple[UUID, str, str]] = []
        # Set by tests that need `start` to behave as "an existing session was found".
        self.resume_started = False

    async def list_scenarios(
        self, *, caller_group_chat_id: str | None = None
    ) -> list[ScenarioDefinition]:
        del caller_group_chat_id
        return self._scenarios

    async def get_active(self, *, owner_kind: str, owner_id: UUID) -> ScenarioSession | None:
        del owner_kind, owner_id
        return self._active

    async def start(
        self,
        *,
        owner_kind: str,
        owner_id: UUID,
        scenario_id: str,
        caller_group_chat_id: str | None = None,
    ) -> PlaythroughStart | None:
        del caller_group_chat_id
        self.started.append((owner_kind, owner_id, scenario_id))
        scenario = self._known.get(scenario_id)
        if scenario is None:
            return None
        session = _session(owner_kind=owner_kind, owner_id=owner_id)
        self._active = session
        return PlaythroughStart(
            session=session,
            scenario=scenario,
            opening=scenario.initial_context,
            resumed=self.resume_started,
        )

    async def restart(self, *, owner_kind: str, owner_id: UUID) -> PlaythroughStart | None:
        self.restarted.append((owner_kind, owner_id))
        if self._active is None:
            return None
        scenario = next(iter(self._known.values()))
        # A restart carries the player's persona forward, which is why it never re-asks.
        session = _session(
            owner_kind=owner_kind,
            owner_id=owner_id,
            user_persona_name=self._active.user_persona_name,
        )
        self._active = session
        return PlaythroughStart(
            session=session, scenario=scenario, opening=scenario.initial_context
        )

    async def clear(self, *, owner_kind: str, owner_id: UUID) -> PlaythroughStart | None:
        self.cleared.append((owner_kind, owner_id))
        if self._active is None:
            return None
        scenario = next(iter(self._known.values()))
        session = _session(owner_kind=owner_kind, owner_id=owner_id)
        self._active = session
        return PlaythroughStart(
            session=session, scenario=scenario, opening=scenario.initial_context
        )

    async def set_persona(
        self, *, session_id: UUID, name: str, description: str = ""
    ) -> PlaythroughStart | None:
        self.personas.append((session_id, name, description))
        if self._active is None or self._active.id != session_id:
            return None
        scenario = next(iter(self._known.values()))
        self._active = self._active.with_persona(name=name, description=description)
        return PlaythroughStart(
            session=self._active, scenario=scenario, opening=scenario.initial_context
        )

    async def resume_text(self, *, session: ScenarioSession) -> str | None:
        del session
        return self._resume


class FakeSessionDirectiveService:
    """Records directive writes; mirrors `SessionDirectiveService`'s domain-backed
    behavior so the adapter's replies are exercised against real rule-id allocation."""

    def __init__(self) -> None:
        self.directives = SessionDirectives()
        self.calls: list[tuple[str, str]] = []

    async def set_language(
        self, *, session: ScenarioSession, language: str
    ) -> SessionDirectives:
        del session
        self.calls.append(("language", language))
        self.directives = self.directives.with_language(language)
        return self.directives

    async def add_rule(self, *, session: ScenarioSession, text: str) -> ScenarioRule:
        self.calls.append(("add_rule", text))
        self.directives, rule = session.directives.with_rule(text)
        return rule

    async def remove_rule(self, *, session: ScenarioSession, rule_id: str) -> bool:
        self.calls.append(("remove_rule", rule_id))
        updated = session.directives.without_rule(rule_id)
        if updated is None:
            return False
        self.directives = updated
        return True

    async def set_director_instruction(
        self, *, session: ScenarioSession, instruction: str
    ) -> SessionDirectives:
        self.calls.append(("director", instruction))
        self.directives = session.directives.with_director_instruction(instruction)
        return self.directives


@dataclass
class FakeUser:
    id: int
    username: str | None = None
    full_name: str = "Test User"
    first_name: str | None = "Test"
    last_name: str | None = "User"
    persona_display_name: str | None = None


@dataclass
class FakeChat:
    id: int
    type: str


@dataclass
class _SentMessage:
    message_id: int


class FakeMessage:
    _next_id = 1000

    def __init__(self, text: str | None) -> None:
        self.text = text
        self.responses: list[str] = []

    async def reply_text(self, text: str) -> _SentMessage:
        self.responses.append(text)
        FakeMessage._next_id += 1
        return _SentMessage(message_id=FakeMessage._next_id)


class FakeNarratorStore:
    def __init__(self) -> None:
        self.data: dict[str, list[int]] = {}

    async def get(self, *, chat_id: str) -> list[int]:
        return list(self.data.get(chat_id, []))

    async def set(self, *, chat_id: str, message_ids: list[int]) -> None:
        self.data[chat_id] = list(message_ids)

    async def clear(self, *, chat_id: str) -> None:
        self.data.pop(chat_id, None)


class FakePendingPersonaStore:
    def __init__(self) -> None:
        self.data: dict[tuple[str, str], UUID] = {}

    async def get(self, *, owner_kind: str, owner_id: str) -> UUID | None:
        return self.data.get((owner_kind, owner_id))

    async def set(self, *, owner_kind: str, owner_id: str, session_id: UUID) -> None:
        self.data[(owner_kind, owner_id)] = session_id

    async def clear(self, *, owner_kind: str, owner_id: str) -> None:
        self.data.pop((owner_kind, owner_id), None)


@dataclass
class FakeUpdate:
    effective_message: FakeMessage | None
    effective_user: FakeUser | None
    effective_chat: FakeChat | None


@dataclass
class FakeChatMember:
    status: str


class FakeBot:
    def __init__(self, member_status: str = "member") -> None:
        self._member_status = member_status
        self.send_message = AsyncMock()
        self.delete_message = AsyncMock()

    async def get_chat_member(self, *, chat_id: int, user_id: int) -> FakeChatMember:
        del chat_id, user_id
        return FakeChatMember(status=self._member_status)


@dataclass
class FakeContext:
    bot: FakeBot


def _make_adapter(
    *,
    chat_service: Any,
    playthrough_service: Any,
    authorization: TelegramAuthorization,
    admin_telegram_user_id: str = "",
    beta_registry: TelegramBetaRegistry | None = None,
    narrator_store: FakeNarratorStore | None = None,
    session_directive_service: FakeSessionDirectiveService | None = None,
    pending_persona_store: FakePendingPersonaStore | None = None,
) -> TelegramAdapter:
    return TelegramAdapter(
        chat_service=chat_service,
        identity_resolver=FakeIdentityResolver(),
        group_identity_resolver=FakeGroupIdentityResolver(),
        playthrough_service=playthrough_service,
        session_directive_service=session_directive_service
        or FakeSessionDirectiveService(),
        authorization=authorization,
        unauthorized_message="not authorized",
        message_max_length=3800,
        admin_telegram_user_id=admin_telegram_user_id,
        beta_registry=beta_registry,
        narrator_store=cast(Any, narrator_store or FakeNarratorStore()),
        pending_persona_store=cast(Any, pending_persona_store or FakePendingPersonaStore()),
    )


def _private_update(text: str, *, user_id: int = 42) -> FakeUpdate:
    return FakeUpdate(
        effective_message=FakeMessage(text=text),
        effective_user=FakeUser(id=user_id),
        effective_chat=FakeChat(id=user_id, type="private"),
    )


def _group_update(text: str, *, chat_id: int = -555, user_id: int = 42) -> FakeUpdate:
    return FakeUpdate(
        effective_message=FakeMessage(text=text),
        effective_user=FakeUser(id=user_id),
        effective_chat=FakeChat(id=chat_id, type="group"),
    )


def _write_beta_request_file(
    *,
    base_path: Path,
    telegram_id: int,
    requested_at: str,
    username: str | None = None,
    first_name: str | None = None,
    last_name: str | None = None,
) -> None:
    request_path = base_path / "telegram" / "beta_requests" / f"{telegram_id}.json"
    request_path.parent.mkdir(parents=True, exist_ok=True)
    request_path.write_text(
        json.dumps(
            {
                "telegram_id": telegram_id,
                "username": username,
                "first_name": first_name,
                "last_name": last_name,
                "requested_at": requested_at,
                "status": "waiting_for_beta_seat",
            },
            ensure_ascii=True,
            indent=2,
        ),
        encoding="utf-8",
    )


# --------------------------------------------------------------------------- #
# Authorization + /start + /help + /beta
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_non_text_messages_are_ignored() -> None:
    chat_service = AsyncMock()
    adapter = _make_adapter(
        chat_service=chat_service,
        playthrough_service=FakePlaythroughService(),
        authorization=TelegramAuthorization({"42"}),
    )
    update = FakeUpdate(
        effective_message=FakeMessage(text=None),
        effective_user=FakeUser(id=42),
        effective_chat=FakeChat(id=42, type="private"),
    )
    await adapter.handle_message(cast(Update, update), cast(Any, None))
    chat_service.send_message.assert_not_awaited()


@pytest.mark.asyncio
async def test_unauthorized_user_gets_configured_message() -> None:
    chat_service = AsyncMock()
    adapter = _make_adapter(
        chat_service=chat_service,
        playthrough_service=FakePlaythroughService(),
        authorization=TelegramAuthorization({"999"}),
    )
    update = _private_update("hello there")
    await adapter.handle_message(cast(Update, update), cast(Any, None))
    assert update.effective_message is not None
    assert update.effective_message.responses == ["not authorized"]
    chat_service.send_message.assert_not_awaited()


@pytest.mark.asyncio
async def test_unauthorized_start_shows_beta_invite(tmp_path: Path) -> None:
    chat_service = AsyncMock()
    registry = TelegramBetaRegistry(base_path=tmp_path)
    adapter = _make_adapter(
        chat_service=chat_service,
        playthrough_service=FakePlaythroughService(),
        authorization=TelegramAuthorization({"123"}),
        beta_registry=registry,
    )
    update = _private_update("/start", user_id=999)
    await adapter.handle_message(cast(Update, update), cast(Any, None))
    assert update.effective_message is not None
    response = update.effective_message.responses[0]
    assert "closed beta" in response
    assert "Use /beta" in response
    # /start must not silently create a beta request.
    assert not (tmp_path / "telegram" / "beta_requests" / "999.json").exists()


@pytest.mark.asyncio
async def test_start_authorized_without_active_invites_scenarios() -> None:
    adapter = _make_adapter(
        chat_service=AsyncMock(),
        playthrough_service=FakePlaythroughService(active=None),
        authorization=TelegramAuthorization({"42"}),
    )
    update = _private_update("/start")
    await adapter.handle_message(cast(Update, update), cast(Any, None))
    assert update.effective_message is not None
    assert update.effective_message.responses == [AUTHORIZED_START_NO_PLAY_MESSAGE]


@pytest.mark.asyncio
async def test_start_authorized_with_active_resumes() -> None:
    adapter = _make_adapter(
        chat_service=AsyncMock(),
        playthrough_service=FakePlaythroughService(
            active=_session(), resume="The hall is silent."
        ),
        authorization=TelegramAuthorization({"42"}),
    )
    update = _private_update("/start")
    await adapter.handle_message(cast(Update, update), cast(Any, None))
    assert update.effective_message is not None
    assert update.effective_message.responses == [
        f"{AUTHORIZED_START_RESUME_MESSAGE}The hall is silent."
    ]


@pytest.mark.asyncio
async def test_help_is_authorization_aware() -> None:
    adapter_unauth = _make_adapter(
        chat_service=AsyncMock(),
        playthrough_service=FakePlaythroughService(),
        authorization=TelegramAuthorization({"999"}),
    )
    unauth = _private_update("/help")
    await adapter_unauth.handle_message(cast(Update, unauth), cast(Any, None))
    assert unauth.effective_message is not None
    assert unauth.effective_message.responses == [build_help_message(authorized=False)]

    adapter_auth = _make_adapter(
        chat_service=AsyncMock(),
        playthrough_service=FakePlaythroughService(),
        authorization=TelegramAuthorization({"42"}),
    )
    auth = _private_update("/help")
    await adapter_auth.handle_message(cast(Update, auth), cast(Any, None))
    assert auth.effective_message is not None
    assert auth.effective_message.responses == [build_help_message(authorized=True)]
    assert "/scenarios" in auth.effective_message.responses[0]


@pytest.mark.asyncio
async def test_beta_creates_request_then_reports_existing(tmp_path: Path) -> None:
    registry = TelegramBetaRegistry(base_path=tmp_path)
    adapter = _make_adapter(
        chat_service=AsyncMock(),
        playthrough_service=FakePlaythroughService(),
        authorization=TelegramAuthorization({"123"}),
        beta_registry=registry,
    )
    first = _private_update("/beta", user_id=999)
    await adapter.handle_message(cast(Update, first), cast(Any, None))
    assert first.effective_message is not None
    assert "recorded" in first.effective_message.responses[0]

    second = _private_update("/beta", user_id=999)
    await adapter.handle_message(cast(Update, second), cast(Any, None))
    assert second.effective_message is not None
    assert "already on the closed beta waiting list" in second.effective_message.responses[0]


# --------------------------------------------------------------------------- #
# /scenarios + /play + /restart
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_scenarios_lists_catalog() -> None:
    scenarios = [
        _scenario("vault", name="The Vault", opening="o", description="A heist."),
        _scenario("manor", name="The Manor", opening="o", description="A haunting."),
    ]
    adapter = _make_adapter(
        chat_service=AsyncMock(),
        playthrough_service=FakePlaythroughService(scenarios=scenarios),
        authorization=TelegramAuthorization({"42"}),
    )
    update = _private_update("/scenarios")
    await adapter.handle_message(cast(Update, update), cast(Any, None))
    assert update.effective_message is not None
    text = update.effective_message.responses[0]
    assert "The Vault" in text and "/play vault" in text
    assert "The Manor" in text and "/play manor" in text


@pytest.mark.asyncio
async def test_play_on_a_new_session_asks_for_a_persona_before_the_opening() -> None:
    scenario = _scenario("vault", name="The Vault", opening="You face the door.")
    playthrough = FakePlaythroughService(known={"vault": scenario})
    pending = FakePendingPersonaStore()
    adapter = _make_adapter(
        chat_service=AsyncMock(),
        playthrough_service=playthrough,
        authorization=TelegramAuthorization({"42"}),
        pending_persona_store=pending,
    )
    update = _private_update("/play vault")
    await adapter.handle_message(cast(Update, update), cast(Any, None))
    assert playthrough.started == [("user", FIXED_USER_ID, "vault")]
    assert update.effective_message is not None
    text = update.effective_message.responses[0]
    assert text == PERSONA_PROMPT_MESSAGE
    # The intro is withheld until the player has answered.
    assert "You face the door." not in text
    assert pending.data == {("user", str(FIXED_USER_ID)): FIXED_SESSION_ID}


@pytest.mark.asyncio
async def test_persona_reply_sets_name_and_description_then_sends_the_opening() -> None:
    scenario = _scenario("vault", name="The Vault", opening="You face the door.")
    playthrough = FakePlaythroughService(known={"vault": scenario})
    pending = FakePendingPersonaStore()
    adapter = _make_adapter(
        chat_service=AsyncMock(),
        playthrough_service=playthrough,
        authorization=TelegramAuthorization({"42"}),
        pending_persona_store=pending,
    )
    await adapter.handle_message(cast(Update, _private_update("/play vault")), cast(Any, None))

    reply = _private_update("Sera Vane\nA wary courier.\nLoves rain, hates crowds.")
    await adapter.handle_message(cast(Update, reply), cast(Any, None))

    assert playthrough.personas == [
        (FIXED_SESSION_ID, "Sera Vane", "A wary courier.\nLoves rain, hates crowds.")
    ]
    assert reply.effective_message is not None
    text = reply.effective_message.responses[0]
    assert "You are playing Sera Vane." in text
    assert "The Vault" in text and "You face the door." in text
    # The pending state is consumed, so the next message is ordinary play.
    assert pending.data == {}


@pytest.mark.asyncio
async def test_skip_uses_the_telegram_name_and_no_description() -> None:
    scenario = _scenario("vault", name="The Vault", opening="You face the door.")
    playthrough = FakePlaythroughService(known={"vault": scenario})
    adapter = _make_adapter(
        chat_service=AsyncMock(),
        playthrough_service=playthrough,
        authorization=TelegramAuthorization({"42"}),
    )
    await adapter.handle_message(cast(Update, _private_update("/play vault")), cast(Any, None))
    await adapter.handle_message(cast(Update, _private_update("/skip")), cast(Any, None))

    assert playthrough.personas == [(FIXED_SESSION_ID, "Test", "")]


@pytest.mark.asyncio
async def test_blank_persona_reply_asks_again_and_keeps_waiting() -> None:
    scenario = _scenario("vault", name="The Vault", opening="You face the door.")
    playthrough = FakePlaythroughService(known={"vault": scenario})
    pending = FakePendingPersonaStore()
    adapter = _make_adapter(
        chat_service=AsyncMock(),
        playthrough_service=playthrough,
        authorization=TelegramAuthorization({"42"}),
        pending_persona_store=pending,
    )
    await adapter.handle_message(cast(Update, _private_update("/play vault")), cast(Any, None))

    blank = _private_update("   ")
    await adapter.handle_message(cast(Update, blank), cast(Any, None))

    assert playthrough.personas == []
    assert blank.effective_message is not None
    assert blank.effective_message.responses == [PERSONA_NAME_REQUIRED_MESSAGE]
    # Still waiting: a blank reply is not silently taken as a skip.
    assert pending.data == {("user", str(FIXED_USER_ID)): FIXED_SESSION_ID}


@pytest.mark.asyncio
async def test_a_pending_persona_prompt_does_not_block_other_commands() -> None:
    scenario = _scenario("vault", name="The Vault", opening="You face the door.")
    playthrough = FakePlaythroughService(known={"vault": scenario})
    pending = FakePendingPersonaStore()
    adapter = _make_adapter(
        chat_service=AsyncMock(),
        playthrough_service=playthrough,
        authorization=TelegramAuthorization({"42"}),
        pending_persona_store=pending,
    )
    await adapter.handle_message(cast(Update, _private_update("/play vault")), cast(Any, None))

    scenarios = _private_update("/scenarios")
    await adapter.handle_message(cast(Update, scenarios), cast(Any, None))

    assert playthrough.personas == []
    assert pending.data == {("user", str(FIXED_USER_ID)): FIXED_SESSION_ID}


@pytest.mark.asyncio
async def test_play_on_an_existing_session_does_not_ask_for_a_persona() -> None:
    scenario = _scenario("vault", name="The Vault", opening="You face the door.")
    playthrough = FakePlaythroughService(known={"vault": scenario})
    pending = FakePendingPersonaStore()
    adapter = _make_adapter(
        chat_service=AsyncMock(),
        playthrough_service=playthrough,
        authorization=TelegramAuthorization({"42"}),
        pending_persona_store=pending,
    )
    # `resumed=True` is what `PlaythroughService.start` returns for an existing session.
    playthrough.resume_started = True
    update = _private_update("/play vault")
    await adapter.handle_message(cast(Update, update), cast(Any, None))

    assert update.effective_message is not None
    text = update.effective_message.responses[0]
    assert "Resuming: The Vault" in text
    assert pending.data == {}


@pytest.mark.asyncio
async def test_group_play_never_asks_for_a_persona() -> None:
    scenario = _scenario("vault", name="The Vault", opening="You face the door.")
    playthrough = FakePlaythroughService(known={"vault": scenario})
    pending = FakePendingPersonaStore()
    adapter = _make_adapter(
        chat_service=AsyncMock(),
        playthrough_service=playthrough,
        authorization=TelegramAuthorization(set(), {"-555"}),
        pending_persona_store=pending,
    )
    update = _group_update("/play vault")
    await adapter.handle_message(
        cast(Update, update), cast(Any, FakeContext(bot=FakeBot(member_status="administrator")))
    )

    assert update.effective_message is not None
    assert "You face the door." in update.effective_message.responses[0]
    assert pending.data == {}


def test_format_start_labels_resumed_session_as_resuming() -> None:
    scenario = _scenario("vault", name="The Vault", opening="You face the door.")
    session = _session(owner_kind="user", owner_id=FIXED_USER_ID)
    start = PlaythroughStart(
        session=session, scenario=scenario, opening="The door creaks open.", resumed=True
    )
    text = TelegramAdapter._format_start(start, user=User(id=FIXED_USER_ID, display_name="alice"))
    assert text == "Resuming: The Vault\n\nThe door creaks open."


def test_format_start_resolves_the_persona_name_in_the_opening() -> None:
    scenario = _scenario("vault", name="The Vault", opening="x")
    session = _session(user_persona_name="Sera Vane")
    start = PlaythroughStart(
        session=session, scenario=scenario, opening="The guard eyes {{user}} warily."
    )
    text = TelegramAdapter._format_start(start, user=User(id=FIXED_USER_ID, display_name="alice"))
    assert text == "Starting: The Vault\n\nThe guard eyes Sera Vane warily."


def test_format_start_falls_back_to_the_display_name_without_a_persona() -> None:
    scenario = _scenario("vault", name="The Vault", opening="x")
    start = PlaythroughStart(
        session=_session(), scenario=scenario, opening="The guard eyes {{user}} warily."
    )
    text = TelegramAdapter._format_start(start, user=User(id=FIXED_USER_ID, display_name="alice"))
    assert text == "Starting: The Vault\n\nThe guard eyes alice warily."


@pytest.mark.asyncio
async def test_play_unknown_scenario_reports_error() -> None:
    adapter = _make_adapter(
        chat_service=AsyncMock(),
        playthrough_service=FakePlaythroughService(known={}),
        authorization=TelegramAuthorization({"42"}),
    )
    update = _private_update("/play nope")
    await adapter.handle_message(cast(Update, update), cast(Any, None))
    assert update.effective_message is not None
    assert "No scenario 'nope'" in update.effective_message.responses[0]


@pytest.mark.asyncio
async def test_play_without_argument_shows_usage_and_library() -> None:
    scenarios = [_scenario("vault", name="The Vault", opening="o", description="A heist.")]
    adapter = _make_adapter(
        chat_service=AsyncMock(),
        playthrough_service=FakePlaythroughService(scenarios=scenarios),
        authorization=TelegramAuthorization({"42"}),
    )
    update = _private_update("/play")
    await adapter.handle_message(cast(Update, update), cast(Any, None))
    assert update.effective_message is not None
    text = update.effective_message.responses[0]
    assert "Usage: /play <id>" in text
    assert "/play vault" in text


@pytest.mark.asyncio
async def test_play_in_group_requires_admin() -> None:
    scenario = _scenario("vault", name="The Vault", opening="Opening.")
    playthrough = FakePlaythroughService(known={"vault": scenario})
    adapter = _make_adapter(
        chat_service=AsyncMock(),
        playthrough_service=playthrough,
        authorization=TelegramAuthorization(set(), {"-555"}),
    )

    member = _group_update("/play vault")
    await adapter.handle_message(cast(Update, member), cast(Any, FakeContext(FakeBot("member"))))
    assert member.effective_message is not None
    assert member.effective_message.responses == [GROUP_ADMIN_ONLY_MESSAGE]
    assert playthrough.started == []

    admin = _group_update("/play vault")
    await adapter.handle_message(
        cast(Update, admin), cast(Any, FakeContext(FakeBot("administrator")))
    )
    assert playthrough.started == [("group", FIXED_GROUP_ID, "vault")]


@pytest.mark.asyncio
async def test_restart_requires_active_and_restarts() -> None:
    scenario = _scenario("vault", name="The Vault", opening="Fresh start.")
    # No active playthrough -> prompt to browse.
    no_active = _make_adapter(
        chat_service=AsyncMock(),
        playthrough_service=FakePlaythroughService(active=None, known={"vault": scenario}),
        authorization=TelegramAuthorization({"42"}),
    )
    update = _private_update("/restart")
    await no_active.handle_message(cast(Update, update), cast(Any, None))
    assert update.effective_message is not None
    assert update.effective_message.responses == [NO_ACTIVE_PLAYTHROUGH_MESSAGE]

    # With an active playthrough -> restart and send opening.
    playthrough = FakePlaythroughService(active=_session(), known={"vault": scenario})
    active = _make_adapter(
        chat_service=AsyncMock(),
        playthrough_service=playthrough,
        authorization=TelegramAuthorization({"42"}),
    )
    restart_update = _private_update("/restart")
    await active.handle_message(cast(Update, restart_update), cast(Any, None))
    assert playthrough.restarted == [("user", FIXED_USER_ID)]
    assert restart_update.effective_message is not None
    assert "Restarted" in restart_update.effective_message.responses[0]
    assert "Fresh start." in restart_update.effective_message.responses[0]


@pytest.mark.asyncio
async def test_restart_does_not_re_prompt_for_a_persona() -> None:
    """ADR-025: a restart carries the player's character forward, so it shows the intro
    straight away — /clear is the tier that asks again."""
    scenario = _scenario("vault", name="The Vault", opening="Fresh start.")
    playthrough = FakePlaythroughService(
        active=_session(user_persona_name="Sera Vane"), known={"vault": scenario}
    )
    pending = FakePendingPersonaStore()
    adapter = _make_adapter(
        chat_service=AsyncMock(),
        playthrough_service=playthrough,
        authorization=TelegramAuthorization({"42"}),
        pending_persona_store=pending,
    )
    update = _private_update("/restart")
    await adapter.handle_message(cast(Update, update), cast(Any, None))

    assert update.effective_message is not None
    assert "Restarted" in update.effective_message.responses[0]
    assert pending.data == {}


@pytest.mark.asyncio
async def test_clear_confirms_before_resetting_anything() -> None:
    scenario = _scenario("vault", name="The Vault", opening="Fresh start.")
    playthrough = FakePlaythroughService(active=_session(), known={"vault": scenario})
    pending = FakePendingPersonaStore()
    adapter = _make_adapter(
        chat_service=AsyncMock(),
        playthrough_service=playthrough,
        authorization=TelegramAuthorization({"42"}),
        pending_persona_store=pending,
    )
    update = _private_update("/clear")
    await adapter.handle_message(cast(Update, update), cast(Any, None))

    assert playthrough.cleared == []
    assert pending.data == {}
    assert update.effective_message is not None
    assert update.effective_message.responses == [CLEAR_CONFIRM_MESSAGE]


@pytest.mark.asyncio
async def test_clear_confirm_resets_and_asks_for_a_new_persona() -> None:
    scenario = _scenario("vault", name="The Vault", opening="Fresh start.")
    playthrough = FakePlaythroughService(
        active=_session(user_persona_name="Sera Vane"), known={"vault": scenario}
    )
    pending = FakePendingPersonaStore()
    adapter = _make_adapter(
        chat_service=AsyncMock(),
        playthrough_service=playthrough,
        authorization=TelegramAuthorization({"42"}),
        pending_persona_store=pending,
    )
    update = _private_update("/clear confirm")
    await adapter.handle_message(cast(Update, update), cast(Any, None))

    assert playthrough.cleared == [("user", FIXED_USER_ID)]
    assert update.effective_message is not None
    assert update.effective_message.responses == [PERSONA_PROMPT_MESSAGE]
    assert pending.data == {("user", str(FIXED_USER_ID)): FIXED_SESSION_ID}


@pytest.mark.asyncio
async def test_clear_in_a_group_is_admin_only() -> None:
    scenario = _scenario("vault", name="The Vault", opening="Fresh start.")
    playthrough = FakePlaythroughService(active=_session(), known={"vault": scenario})
    adapter = _make_adapter(
        chat_service=AsyncMock(),
        playthrough_service=playthrough,
        authorization=TelegramAuthorization(set(), {"-555"}),
    )
    update = _group_update("/clear confirm")
    await adapter.handle_message(
        cast(Update, update), cast(Any, FakeContext(bot=FakeBot(member_status="member")))
    )

    assert playthrough.cleared == []
    assert update.effective_message is not None
    assert update.effective_message.responses == [GROUP_ADMIN_ONLY_MESSAGE]


# --------------------------------------------------------------------------- #
# Story interaction: /continue, /retry, /chat, plain messages
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_continue_calls_continue_story() -> None:
    chat_service = AsyncMock()
    chat_service.continue_story = AsyncMock(return_value="the story advances")
    adapter = _make_adapter(
        chat_service=chat_service,
        playthrough_service=FakePlaythroughService(active=_session()),
        authorization=TelegramAuthorization({"42"}),
    )
    update = _private_update("/continue")
    await adapter.handle_message(cast(Update, update), cast(Any, None))
    chat_service.continue_story.assert_awaited_once()
    assert update.effective_message is not None
    assert update.effective_message.responses == ["the story advances"]


@pytest.mark.asyncio
async def test_retry_calls_regenerate_last_response() -> None:
    chat_service = AsyncMock()
    chat_service.regenerate_last_response = AsyncMock(return_value="a new take")
    adapter = _make_adapter(
        chat_service=chat_service,
        playthrough_service=FakePlaythroughService(active=_session()),
        authorization=TelegramAuthorization({"42"}),
    )
    update = _private_update("/retry")
    await adapter.handle_message(cast(Update, update), cast(Any, FakeContext(FakeBot())))
    chat_service.regenerate_last_response.assert_awaited_once()
    assert update.effective_message is not None
    assert update.effective_message.responses == ["a new take"]


@pytest.mark.asyncio
async def test_narrator_reply_is_tracked_for_retry() -> None:
    chat_service = AsyncMock()
    chat_service.send_message = AsyncMock(return_value="the story reply")
    store = FakeNarratorStore()
    adapter = _make_adapter(
        chat_service=chat_service,
        playthrough_service=FakePlaythroughService(active=_session()),
        authorization=TelegramAuthorization({"42"}),
        narrator_store=store,
    )
    update = _private_update("I open the door", user_id=42)
    await adapter.handle_message(cast(Update, update), cast(Any, None))

    # The narrator reply's telegram message id was recorded for chat "42".
    assert store.data["42"]
    assert update.effective_message is not None
    assert update.effective_message.responses == ["the story reply"]


@pytest.mark.asyncio
async def test_retry_deletes_previous_message_and_records_new_one() -> None:
    chat_service = AsyncMock()
    chat_service.regenerate_last_response = AsyncMock(return_value="regenerated take")
    store = FakeNarratorStore()
    store.data["42"] = [777]  # a previously-sent narrator message
    adapter = _make_adapter(
        chat_service=chat_service,
        playthrough_service=FakePlaythroughService(active=_session()),
        authorization=TelegramAuthorization({"42"}),
        narrator_store=store,
    )
    bot = FakeBot()
    update = _private_update("/retry", user_id=42)
    await adapter.handle_message(cast(Update, update), cast(Any, FakeContext(bot)))

    # The previous narrator message was deleted in place...
    bot.delete_message.assert_awaited_once_with(chat_id=42, message_id=777)
    # ...the regenerated reply was sent...
    assert update.effective_message is not None
    assert update.effective_message.responses == ["regenerated take"]
    # ...and the new message id replaced the old one (no longer 777).
    assert store.data["42"] and store.data["42"] != [777]


@pytest.mark.asyncio
async def test_commands_without_active_playthrough_prompt_to_play() -> None:
    chat_service = AsyncMock()
    adapter = _make_adapter(
        chat_service=chat_service,
        playthrough_service=FakePlaythroughService(active=None),
        authorization=TelegramAuthorization({"42"}),
    )
    update = _private_update("/continue")
    await adapter.handle_message(cast(Update, update), cast(Any, None))
    chat_service.continue_story.assert_not_awaited()
    assert update.effective_message is not None
    assert update.effective_message.responses == [NO_ACTIVE_PLAYTHROUGH_MESSAGE]


@pytest.mark.asyncio
async def test_group_member_cannot_continue_but_admin_can() -> None:
    chat_service = AsyncMock()
    chat_service.continue_story = AsyncMock(return_value="advanced")
    adapter = _make_adapter(
        chat_service=chat_service,
        playthrough_service=FakePlaythroughService(
            active=_session(owner_kind="group", owner_id=FIXED_GROUP_ID)
        ),
        authorization=TelegramAuthorization(set(), {"-555"}),
    )

    member = _group_update("/continue")
    await adapter.handle_message(cast(Update, member), cast(Any, FakeContext(FakeBot("member"))))
    chat_service.continue_story.assert_not_awaited()
    assert member.effective_message is not None
    assert member.effective_message.responses == [GROUP_ADMIN_ONLY_MESSAGE]

    admin = _group_update("/continue")
    await adapter.handle_message(
        cast(Update, admin), cast(Any, FakeContext(FakeBot("administrator")))
    )
    chat_service.continue_story.assert_awaited_once()


@pytest.mark.asyncio
async def test_chat_command_in_group_forwards_stripped_text_with_group_metadata() -> None:
    chat_service = AsyncMock()
    chat_service.send_message = AsyncMock(return_value="group reply")
    adapter = _make_adapter(
        chat_service=chat_service,
        playthrough_service=FakePlaythroughService(
            active=_session(owner_kind="group", owner_id=FIXED_GROUP_ID)
        ),
        authorization=TelegramAuthorization(set(), {"-555"}),
    )
    update = _group_update("/chat   let's go inside  ", user_id=7)
    await adapter.handle_message(cast(Update, update), cast(Any, FakeContext(FakeBot("member"))))

    chat_service.send_message.assert_awaited_once()
    kwargs = chat_service.send_message.await_args.kwargs
    assert kwargs["message"] == "let's go inside"
    assert kwargs["user_id"] == str(FIXED_USER_ID)
    assert update.effective_message is not None
    assert update.effective_message.responses == ["group reply"]


@pytest.mark.asyncio
async def test_plain_message_in_group_is_ignored() -> None:
    chat_service = AsyncMock()
    adapter = _make_adapter(
        chat_service=chat_service,
        playthrough_service=FakePlaythroughService(
            active=_session(owner_kind="group", owner_id=FIXED_GROUP_ID)
        ),
        authorization=TelegramAuthorization(set(), {"-555"}),
    )
    update = _group_update("just chatting to the room")
    await adapter.handle_message(cast(Update, update), cast(Any, FakeContext(FakeBot("member"))))
    chat_service.send_message.assert_not_awaited()
    assert update.effective_message is not None
    assert update.effective_message.responses == []


@pytest.mark.asyncio
async def test_plain_message_in_private_calls_send_message() -> None:
    chat_service = AsyncMock()
    chat_service.send_message = AsyncMock(return_value="scene reply")
    adapter = _make_adapter(
        chat_service=chat_service,
        playthrough_service=FakePlaythroughService(active=_session()),
        authorization=TelegramAuthorization({"42"}),
    )
    update = _private_update("I push the door open")
    await adapter.handle_message(cast(Update, update), cast(Any, None))
    chat_service.send_message.assert_awaited_once()
    assert chat_service.send_message.await_args.kwargs["message"] == "I push the door open"
    assert update.effective_message is not None
    assert update.effective_message.responses == ["scene reply"]


@pytest.mark.asyncio
async def test_unsupported_command_is_reported() -> None:
    chat_service = AsyncMock()
    adapter = _make_adapter(
        chat_service=chat_service,
        playthrough_service=FakePlaythroughService(active=_session()),
        authorization=TelegramAuthorization({"42"}),
    )
    update = _private_update("/regenerate")
    await adapter.handle_message(cast(Update, update), cast(Any, None))
    chat_service.send_message.assert_not_awaited()
    assert update.effective_message is not None
    assert "Unsupported command" in update.effective_message.responses[0]


@pytest.mark.asyncio
async def test_cancel_acknowledges() -> None:
    adapter = _make_adapter(
        chat_service=AsyncMock(),
        playthrough_service=FakePlaythroughService(),
        authorization=TelegramAuthorization({"42"}),
    )
    update = _private_update("/cancel")
    await adapter.handle_message(cast(Update, update), cast(Any, None))
    assert update.effective_message is not None
    assert update.effective_message.responses == ["Nothing to cancel."]


@pytest.mark.asyncio
async def test_long_response_is_split_into_multiple_messages() -> None:
    chat_service = AsyncMock()
    chat_service.send_message = AsyncMock(return_value="x" * 9000)
    adapter = _make_adapter(
        chat_service=chat_service,
        playthrough_service=FakePlaythroughService(active=_session()),
        authorization=TelegramAuthorization({"42"}),
    )
    update = _private_update("go on")
    await adapter.handle_message(cast(Update, update), cast(Any, None))
    assert update.effective_message is not None
    assert len(update.effective_message.responses) > 1


@pytest.mark.asyncio
async def test_llm_connection_error_is_reported() -> None:
    chat_service = AsyncMock()
    chat_service.send_message = AsyncMock(side_effect=LLMConnectionError("down"))
    adapter = _make_adapter(
        chat_service=chat_service,
        playthrough_service=FakePlaythroughService(active=_session()),
        authorization=TelegramAuthorization({"42"}),
    )
    update = _private_update("hello")
    await adapter.handle_message(cast(Update, update), cast(Any, None))
    assert update.effective_message is not None
    assert "unavailable" in update.effective_message.responses[0]


# --------------------------------------------------------------------------- #
# Admin beta management (unchanged behavior)
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_admin_can_list_pending_requests_in_chronological_order(tmp_path: Path) -> None:
    registry = TelegramBetaRegistry(base_path=tmp_path)
    _write_beta_request_file(
        base_path=tmp_path,
        telegram_id=987654321,
        requested_at="2026-07-16T09:18:00+00:00",
        username="AnotherUser",
        first_name="Alice",
    )
    _write_beta_request_file(
        base_path=tmp_path,
        telegram_id=123456789,
        requested_at="2026-07-15T13:42:00+00:00",
        username="PabloDonkey",
        first_name="Pablo",
    )
    adapter = _make_adapter(
        chat_service=AsyncMock(),
        playthrough_service=FakePlaythroughService(),
        authorization=TelegramAuthorization({"42"}),
        admin_telegram_user_id="1",
        beta_registry=registry,
    )
    update = _private_update("/admin_beta_list", user_id=1)
    await adapter.handle_message(cast(Update, update), cast(Any, FakeContext(FakeBot())))
    assert update.effective_message is not None
    response = update.effective_message.responses[0]
    assert "Pending Beta Requests" in response
    assert response.index("Telegram ID: 123456789") < response.index("Telegram ID: 987654321")


@pytest.mark.asyncio
async def test_non_admin_cannot_list_pending_requests(tmp_path: Path) -> None:
    registry = TelegramBetaRegistry(base_path=tmp_path)
    _write_beta_request_file(
        base_path=tmp_path, telegram_id=123456789, requested_at="2026-07-15T13:42:00+00:00"
    )
    adapter = _make_adapter(
        chat_service=AsyncMock(),
        playthrough_service=FakePlaythroughService(),
        authorization=TelegramAuthorization({"42"}),
        admin_telegram_user_id="1",
        beta_registry=registry,
    )
    update = _private_update("/admin_beta_list", user_id=2)
    await adapter.handle_message(cast(Update, update), cast(Any, FakeContext(FakeBot())))
    assert update.effective_message is not None
    assert update.effective_message.responses == []


@pytest.mark.asyncio
async def test_admin_can_approve_by_telegram_id_and_persist_authorization(tmp_path: Path) -> None:
    registry = TelegramBetaRegistry(base_path=tmp_path)
    await registry.create_request(
        telegram_id=999, username="PabloDonkey", first_name="Pablo", last_name="Smith"
    )
    authorization_dir = tmp_path / "telegram" / "authorization"
    adapter = _make_adapter(
        chat_service=AsyncMock(),
        playthrough_service=FakePlaythroughService(),
        authorization=TelegramAuthorization.from_directory(authorization_dir),
        admin_telegram_user_id="1",
        beta_registry=registry,
    )
    bot = FakeBot()
    update = _private_update("/admin_beta_accept 999", user_id=1)
    await adapter.handle_message(cast(Update, update), cast(Any, FakeContext(bot)))

    assert update.effective_message is not None
    assert update.effective_message.responses == [
        "Approved Telegram ID 999 and updated authorization."
    ]
    assert not (tmp_path / "telegram" / "beta_requests" / "999.json").exists()
    users_payload = json.loads((authorization_dir / "users.json").read_text(encoding="utf-8"))
    assert users_payload["allowed_user_ids"] == ["999"]
    bot.send_message.assert_awaited_once()


@pytest.mark.asyncio
async def test_admin_can_reject_pending_request_and_archive_reason(tmp_path: Path) -> None:
    registry = TelegramBetaRegistry(base_path=tmp_path)
    await registry.create_request(
        telegram_id=888, username="reject_me", first_name="Reject", last_name="Me"
    )
    adapter = _make_adapter(
        chat_service=AsyncMock(),
        playthrough_service=FakePlaythroughService(),
        authorization=TelegramAuthorization({"42"}),
        admin_telegram_user_id="1",
        beta_registry=registry,
    )
    update = _private_update("/admin_beta_reject 888 incomplete_profile", user_id=1)
    await adapter.handle_message(cast(Update, update), cast(Any, FakeContext(FakeBot())))

    assert update.effective_message is not None
    assert update.effective_message.responses == ["Rejected Telegram ID 888."]
    assert not (tmp_path / "telegram" / "beta_requests" / "888.json").exists()
    archived_payload = json.loads(
        (tmp_path / "telegram" / "beta_rejected" / "888.json").read_text(encoding="utf-8")
    )
    assert archived_payload["status"] == "rejected"
    assert archived_payload["rejection_reason"] == "incomplete_profile"


# --------------------------------------------------------------------------- #
# Identity resolution
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("user", "expected_display_name"),
    [
        (FakeUser(id=77, username="alice", first_name="Alice", last_name="A"), "alice"),
        (FakeUser(id=77, username=None, first_name="Alice", last_name="A"), "Alice"),
        (FakeUser(id=77, username=None, first_name=None, last_name="A"), "telegram_user_77"),
    ],
)
async def test_identity_resolution_uses_display_name_priority(
    user: FakeUser,
    expected_display_name: str,
) -> None:
    chat_service = AsyncMock()
    chat_service.send_message = AsyncMock(return_value="ok")
    identity_resolver = AsyncMock()
    identity_resolver.resolve_identity = AsyncMock(
        return_value=User(id=FIXED_USER_ID, display_name="x")
    )
    adapter = TelegramAdapter(
        chat_service=chat_service,
        identity_resolver=identity_resolver,
        group_identity_resolver=FakeGroupIdentityResolver(),
        playthrough_service=FakePlaythroughService(active=_session()),
        session_directive_service=FakeSessionDirectiveService(),
        authorization=TelegramAuthorization({"77"}),
        unauthorized_message="not authorized",
        message_max_length=3800,
    )
    update = FakeUpdate(
        effective_message=FakeMessage(text="hello"),
        effective_user=user,
        effective_chat=FakeChat(id=77, type="private"),
    )
    await adapter.handle_message(cast(Update, update), cast(Any, None))
    resolve_kwargs = identity_resolver.resolve_identity.await_args.kwargs
    assert resolve_kwargs["display_name"] == expected_display_name


@pytest.mark.asyncio
async def test_identity_resolution_prefers_persona_display_name() -> None:
    chat_service = AsyncMock()
    chat_service.send_message = AsyncMock(return_value="ok")
    identity_resolver = AsyncMock()
    identity_resolver.resolve_identity = AsyncMock(
        return_value=User(id=FIXED_USER_ID, display_name="x")
    )
    adapter = TelegramAdapter(
        chat_service=chat_service,
        identity_resolver=identity_resolver,
        group_identity_resolver=FakeGroupIdentityResolver(),
        playthrough_service=FakePlaythroughService(active=_session()),
        session_directive_service=FakeSessionDirectiveService(),
        authorization=TelegramAuthorization({"77"}),
        unauthorized_message="not authorized",
        message_max_length=3800,
    )
    user = FakeUser(
        id=77,
        username="alice",
        first_name="Alice",
        last_name="A",
        persona_display_name="Captain Alice",
    )
    update = FakeUpdate(
        effective_message=FakeMessage(text="hello"),
        effective_user=user,
        effective_chat=FakeChat(id=77, type="private"),
    )
    await adapter.handle_message(cast(Update, update), cast(Any, None))
    resolve_kwargs = identity_resolver.resolve_identity.await_args.kwargs
    assert resolve_kwargs["display_name"] == "Captain Alice"


def _directive_adapter(
    *,
    directives: SessionDirectives | None = None,
    active: bool = True,
) -> tuple[TelegramAdapter, FakeSessionDirectiveService]:
    service = FakeSessionDirectiveService()
    adapter = _make_adapter(
        chat_service=AsyncMock(),
        playthrough_service=FakePlaythroughService(
            active=_session(directives=directives) if active else None
        ),
        authorization=TelegramAuthorization({"42"}),
        session_directive_service=service,
    )
    return adapter, service


async def _send(adapter: TelegramAdapter, text: str) -> list[str]:
    update = _private_update(text)
    await adapter.handle_message(cast(Update, update), cast(Any, None))
    assert update.effective_message is not None
    return update.effective_message.responses


@pytest.mark.asyncio
async def test_director_sets_a_one_turn_instruction() -> None:
    adapter, service = _directive_adapter()

    responses = await _send(adapter, "/director introduce a stranger")

    assert service.calls == [("director", "introduce a stranger")]
    assert responses == ["Director note set. It shapes the next reply only."]


@pytest.mark.asyncio
async def test_director_without_argument_shows_usage() -> None:
    adapter, service = _directive_adapter()

    responses = await _send(adapter, "/director")

    assert service.calls == []
    assert "Usage: /director <instruction>" in responses[0]


@pytest.mark.asyncio
async def test_director_without_argument_reports_a_queued_note() -> None:
    adapter, service = _directive_adapter(
        directives=SessionDirectives().with_director_instruction("raise the stakes")
    )

    responses = await _send(adapter, "/director")

    assert service.calls == []
    assert "raise the stakes" in responses[0]


@pytest.mark.asyncio
async def test_language_sets_a_supported_code() -> None:
    adapter, service = _directive_adapter()

    responses = await _send(adapter, "/language FR")

    assert service.calls == [("language", "fr")]
    assert "French" in responses[0]


@pytest.mark.asyncio
async def test_language_rejects_an_unsupported_code() -> None:
    adapter, service = _directive_adapter()

    responses = await _send(adapter, "/language klingon")

    assert service.calls == []
    assert "Unsupported language 'klingon'" in responses[0]
    assert "Supported codes:" in responses[0]


@pytest.mark.asyncio
async def test_language_without_argument_reports_the_current_setting() -> None:
    adapter, service = _directive_adapter(directives=SessionDirectives(language="fr"))

    responses = await _send(adapter, "/language")

    assert service.calls == []
    assert "Current language: French (fr)" in responses[0]


@pytest.mark.asyncio
async def test_rule_add_and_remove() -> None:
    adapter, service = _directive_adapter()

    added = await _send(adapter, "/rule add keep replies under 100 words")
    assert service.calls == [("add_rule", "keep replies under 100 words")]
    assert added == ["Rule 1 added: keep replies under 100 words"]

    with_rule, _ = SessionDirectives().with_rule("keep replies under 100 words")
    adapter, service = _directive_adapter(directives=with_rule)

    removed = await _send(adapter, "/rule remove 1")
    assert service.calls == [("remove_rule", "1")]
    assert removed == ["Rule 1 removed."]


@pytest.mark.asyncio
async def test_rule_remove_reports_an_unknown_id() -> None:
    with_rule, _ = SessionDirectives().with_rule("no time skips")
    adapter, _ = _directive_adapter(directives=with_rule)

    responses = await _send(adapter, "/rule remove 9")

    assert "No rule with id 9" in responses[0]


@pytest.mark.asyncio
async def test_rules_lists_and_reports_emptiness() -> None:
    adapter, _ = _directive_adapter()
    empty = await _send(adapter, "/rules")
    assert "haven't set any rules" in empty[0]

    directives, _ = SessionDirectives().with_rule("no time skips")
    directives, _ = directives.with_rule("keep it brief")
    adapter, _ = _directive_adapter(directives=directives)

    listed = await _send(adapter, "/rules")
    assert "1. no time skips" in listed[0]
    assert "2. keep it brief" in listed[0]


@pytest.mark.asyncio
async def test_rule_without_a_valid_subcommand_shows_usage() -> None:
    adapter, service = _directive_adapter()

    for text in ("/rule", "/rule add", "/rule remove", "/rule frobnicate"):
        responses = await _send(adapter, text)
        assert "Usage:" in responses[0], text

    assert service.calls == []


@pytest.mark.asyncio
async def test_directive_commands_need_an_active_playthrough() -> None:
    adapter, service = _directive_adapter(active=False)

    responses = await _send(adapter, "/director do something")

    assert service.calls == []
    assert responses == [NO_ACTIVE_PLAYTHROUGH_MESSAGE]


@pytest.mark.asyncio
async def test_group_member_cannot_set_directives_but_admin_can() -> None:
    service = FakeSessionDirectiveService()
    adapter = _make_adapter(
        chat_service=AsyncMock(),
        playthrough_service=FakePlaythroughService(
            active=_session(owner_kind="group", owner_id=FIXED_GROUP_ID)
        ),
        authorization=TelegramAuthorization(set(), {"-555"}),
        session_directive_service=service,
    )

    member = _group_update("/language fr")
    await adapter.handle_message(cast(Update, member), cast(Any, FakeContext(FakeBot("member"))))
    assert member.effective_message is not None
    assert member.effective_message.responses == [GROUP_ADMIN_ONLY_MESSAGE]
    assert service.calls == []

    admin = _group_update("/language fr")
    await adapter.handle_message(
        cast(Update, admin), cast(Any, FakeContext(FakeBot("administrator")))
    )
    assert service.calls == [("language", "fr")]


@pytest.mark.asyncio
async def test_empty_generation_tells_the_player_instead_of_sending_nothing() -> None:
    """The original failure: `split_message("")` returns `[]`, so the send loop never ran and
    the player got no reply and no error at all."""
    chat_service = AsyncMock()
    chat_service.send_message = AsyncMock(
        side_effect=EmptyGenerationError("empty", finish_reason="length")
    )
    adapter = _make_adapter(
        chat_service=chat_service,
        playthrough_service=FakePlaythroughService(active=_session()),
        authorization=TelegramAuthorization({"42"}),
    )

    responses = await _send(adapter, "hello there")

    assert responses == [EMPTY_GENERATION_MESSAGE]


@pytest.mark.asyncio
async def test_empty_generation_on_continue_is_reported_too() -> None:
    chat_service = AsyncMock()
    chat_service.continue_story = AsyncMock(
        side_effect=EmptyGenerationError("empty", finish_reason="length")
    )
    adapter = _make_adapter(
        chat_service=chat_service,
        playthrough_service=FakePlaythroughService(active=_session()),
        authorization=TelegramAuthorization({"42"}),
    )

    responses = await _send(adapter, "/continue")

    assert responses == [EMPTY_GENERATION_MESSAGE]


@pytest.mark.asyncio
async def test_generic_generation_errors_keep_their_own_message() -> None:
    """EmptyGenerationError subclasses LLMGenerationError, so the arms must not collapse."""
    chat_service = AsyncMock()
    chat_service.send_message = AsyncMock(side_effect=LLMGenerationError("boom"))
    adapter = _make_adapter(
        chat_service=chat_service,
        playthrough_service=FakePlaythroughService(active=_session()),
        authorization=TelegramAuthorization({"42"}),
    )

    responses = await _send(adapter, "hello there")

    assert responses == ["The model failed to generate a reply. Please try again."]
