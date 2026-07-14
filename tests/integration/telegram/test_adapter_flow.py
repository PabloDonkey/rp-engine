from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, cast
from unittest.mock import AsyncMock
from uuid import UUID

import pytest
from telegram import Update

from rp_engine.adapters.telegram.adapter import TelegramAdapter
from rp_engine.adapters.telegram.authorization import TelegramAuthorization
from rp_engine.adapters.telegram.commands import HELP_MESSAGE
from rp_engine.core.group.group import Group
from rp_engine.core.memory.models import ConversationIdentity
from rp_engine.core.services.commands import SelectCharacterCommand
from rp_engine.core.session.session import Session
from rp_engine.core.user.user import User

FIXED_USER_ID = UUID("00000000-0000-0000-0000-000000000042")
FIXED_GROUP_ID = UUID("00000000-0000-0000-0000-000000000555")
FIXED_SESSION_ID = UUID("00000000-0000-0000-0000-000000000099")
FIXED_CREATED_AT = datetime(2026, 7, 12, 0, 0, tzinfo=UTC)


class FakeIdentityResolver:
    async def resolve_identity(
        self,
        *,
        provider: str,
        external_id: str,
        display_name: str,
        metadata: dict[str, str] | None = None,
    ) -> User:
        del provider
        del external_id
        del metadata
        return User(id=FIXED_USER_ID, display_name=display_name)


class FakeCharacterService:
    async def ensure_active_session_for_user(self, *, user_id: UUID) -> Session:
        del user_id
        return Session(
            id=FIXED_SESSION_ID,
            owner_kind="user",
            owner_id=FIXED_USER_ID,
            character_id="default",
            world_id="default",
            created_at=FIXED_CREATED_AT,
        )

    async def ensure_active_session_for_group(self, *, group_id: UUID) -> Session:
        del group_id
        return Session(
            id=FIXED_SESSION_ID,
            owner_kind="group",
            owner_id=FIXED_GROUP_ID,
            character_id="default",
            world_id="default",
            created_at=FIXED_CREATED_AT,
        )

    async def select_character_for_user(
        self,
        *,
        user_id: UUID,
        command: SelectCharacterCommand,
    ) -> Session:
        del user_id
        character_id = command.character_name.lower()
        return Session(
            id=FIXED_SESSION_ID,
            owner_kind="user",
            owner_id=FIXED_USER_ID,
            character_id=character_id,
            world_id="default",
            created_at=FIXED_CREATED_AT,
        )

    async def select_character_for_group(
        self,
        *,
        group_id: UUID,
        command: SelectCharacterCommand,
    ) -> Session:
        del group_id
        character_id = command.character_name.lower()
        return Session(
            id=FIXED_SESSION_ID,
            owner_kind="group",
            owner_id=FIXED_GROUP_ID,
            character_id=character_id,
            world_id="default",
            created_at=FIXED_CREATED_AT,
        )


class FakeGroupIdentityResolver:
    async def resolve_identity(
        self,
        *,
        provider: str,
        external_id: str,
        display_name: str,
        metadata: dict[str, str] | None = None,
    ) -> Group:
        del provider
        del external_id
        del metadata
        return Group(id=FIXED_GROUP_ID, display_name=display_name)


@dataclass
class FakeUser:
    id: int
    username: str | None = None
    full_name: str = "Test User"
    first_name: str | None = "Test"
    last_name: str | None = "User"


@dataclass
class FakeChat:
    id: int
    type: str


class FakeMessage:
    def __init__(self, text: str | None) -> None:
        self.text = text
        self.responses: list[str] = []

    async def reply_text(self, text: str) -> None:
        self.responses.append(text)


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

    async def get_chat_member(self, *, chat_id: int, user_id: int) -> FakeChatMember:
        del chat_id
        del user_id
        return FakeChatMember(status=self._member_status)


@dataclass
class FakeContext:
    bot: FakeBot


@pytest.mark.asyncio
async def test_telegram_adapter_flow_calls_chat_service_and_replies() -> None:
    chat_service = AsyncMock()
    chat_service.send_message = AsyncMock(return_value="bot reply")
    adapter = TelegramAdapter(
        chat_service=chat_service,
        identity_resolver=FakeIdentityResolver(),
        group_identity_resolver=FakeGroupIdentityResolver(),
        character_service=FakeCharacterService(),
        authorization=TelegramAuthorization(set()),
        unauthorized_message="not authorized",
        message_max_length=3800,
    )

    message = FakeMessage(text="hello")
    update = FakeUpdate(
        effective_message=message,
        effective_user=FakeUser(id=42),
        effective_chat=FakeChat(id=42, type="private"),
    )

    await adapter.handle_message(cast(Update, update), cast(Any, None))

    chat_service.send_message.assert_awaited_once()
    send_kwargs = chat_service.send_message.await_args.kwargs
    assert send_kwargs["conversation_identity"] == ConversationIdentity.for_session(
        str(FIXED_SESSION_ID)
    )
    assert send_kwargs["message"] == "hello"
    assert send_kwargs["user_id"] is None
    assert send_kwargs["username"] is None
    assert send_kwargs["display_name"] is None
    assert "processing_feedback" in send_kwargs
    assert message.responses == ["bot reply"]


@pytest.mark.asyncio
async def test_private_flow_uses_user_session_resolution() -> None:
    chat_service = AsyncMock()
    chat_service.send_message = AsyncMock(return_value="ok")

    character_service = AsyncMock()
    character_service.ensure_active_session_for_user = AsyncMock(
        return_value=Session(
            id=FIXED_SESSION_ID,
            owner_kind="user",
            owner_id=FIXED_USER_ID,
            character_id="default",
            world_id="default",
            created_at=FIXED_CREATED_AT,
        )
    )

    adapter = TelegramAdapter(
        chat_service=chat_service,
        identity_resolver=FakeIdentityResolver(),
        group_identity_resolver=FakeGroupIdentityResolver(),
        character_service=character_service,
        authorization=TelegramAuthorization(set()),
        unauthorized_message="not authorized",
        message_max_length=3800,
    )

    update = FakeUpdate(
        effective_message=FakeMessage(text="hello"),
        effective_user=FakeUser(id=42),
        effective_chat=FakeChat(id=42, type="private"),
    )

    await adapter.handle_message(cast(Update, update), cast(Any, None))

    character_service.ensure_active_session_for_user.assert_awaited_once()
    character_service.ensure_active_session_for_group.assert_not_called()


@pytest.mark.asyncio
async def test_group_flow_uses_group_session_resolution() -> None:
    chat_service = AsyncMock()
    chat_service.send_message = AsyncMock(return_value="group ok")

    character_service = AsyncMock()
    character_service.ensure_active_session_for_group = AsyncMock(
        return_value=Session(
            id=FIXED_SESSION_ID,
            owner_kind="group",
            owner_id=FIXED_GROUP_ID,
            character_id="default",
            world_id="default",
            created_at=FIXED_CREATED_AT,
        )
    )

    adapter = TelegramAdapter(
        chat_service=chat_service,
        identity_resolver=FakeIdentityResolver(),
        group_identity_resolver=FakeGroupIdentityResolver(),
        character_service=character_service,
        authorization=TelegramAuthorization(set(), {"-555"}),
        unauthorized_message="not authorized",
        message_max_length=3800,
    )

    update = FakeUpdate(
        effective_message=FakeMessage(text="hello group"),
        effective_user=FakeUser(id=77),
        effective_chat=FakeChat(id=-555, type="group"),
    )

    await adapter.handle_message(cast(Update, update), cast(Any, FakeContext(FakeBot())))

    character_service.ensure_active_session_for_group.assert_awaited_once()
    character_service.ensure_active_session_for_user.assert_not_called()


@pytest.mark.asyncio
async def test_telegram_adapter_ignores_non_text_messages() -> None:
    chat_service = AsyncMock()
    adapter = TelegramAdapter(
        chat_service=chat_service,
        identity_resolver=FakeIdentityResolver(),
        group_identity_resolver=FakeGroupIdentityResolver(),
        character_service=FakeCharacterService(),
        authorization=TelegramAuthorization(set()),
        unauthorized_message="not authorized",
        message_max_length=3800,
    )

    update = FakeUpdate(
        effective_message=FakeMessage(text=None),
        effective_user=FakeUser(id=42),
        effective_chat=FakeChat(id=42, type="private"),
    )

    await adapter.handle_message(cast(Update, update), cast(Any, None))

    chat_service.send_message.assert_not_awaited()


@pytest.mark.asyncio
async def test_help_command_is_handled_in_adapter() -> None:
    chat_service = AsyncMock()
    adapter = TelegramAdapter(
        chat_service=chat_service,
        identity_resolver=FakeIdentityResolver(),
        group_identity_resolver=FakeGroupIdentityResolver(),
        character_service=FakeCharacterService(),
        authorization=TelegramAuthorization(set()),
        unauthorized_message="not authorized",
        message_max_length=3800,
    )

    message = FakeMessage(text="/help")
    update = FakeUpdate(
        effective_message=message,
        effective_user=FakeUser(id=42),
        effective_chat=FakeChat(id=42, type="private"),
    )

    await adapter.handle_message(cast(Update, update), cast(Any, None))

    assert message.responses == [HELP_MESSAGE]
    chat_service.send_message.assert_not_awaited()
    chat_service.continue_story.assert_not_awaited()
    chat_service.clear_conversation.assert_not_awaited()


@pytest.mark.asyncio
async def test_continue_command_calls_continue_story() -> None:
    chat_service = AsyncMock()
    chat_service.continue_story = AsyncMock(return_value="continued")
    adapter = TelegramAdapter(
        chat_service=chat_service,
        identity_resolver=FakeIdentityResolver(),
        group_identity_resolver=FakeGroupIdentityResolver(),
        character_service=FakeCharacterService(),
        authorization=TelegramAuthorization(set()),
        unauthorized_message="not authorized",
        message_max_length=3800,
    )

    message = FakeMessage(text="/continue")
    update = FakeUpdate(
        effective_message=message,
        effective_user=FakeUser(id=9),
        effective_chat=FakeChat(id=9, type="private"),
    )

    await adapter.handle_message(cast(Update, update), cast(Any, None))

    chat_service.continue_story.assert_awaited_once()
    continue_kwargs = chat_service.continue_story.await_args.kwargs
    assert continue_kwargs["conversation_identity"] == ConversationIdentity.for_session(
        str(FIXED_SESSION_ID)
    )
    assert "processing_feedback" in continue_kwargs
    chat_service.send_message.assert_not_awaited()
    assert message.responses == ["continued"]


@pytest.mark.asyncio
async def test_regenerate_command_calls_regenerate_last_response() -> None:
    chat_service = AsyncMock()
    chat_service.regenerate_last_response = AsyncMock(return_value="regenerated")
    adapter = TelegramAdapter(
        chat_service=chat_service,
        identity_resolver=FakeIdentityResolver(),
        group_identity_resolver=FakeGroupIdentityResolver(),
        character_service=FakeCharacterService(),
        authorization=TelegramAuthorization(set()),
        unauthorized_message="not authorized",
        message_max_length=3800,
    )

    message = FakeMessage(text="/regenerate")
    update = FakeUpdate(
        effective_message=message,
        effective_user=FakeUser(id=9),
        effective_chat=FakeChat(id=9, type="private"),
    )

    await adapter.handle_message(cast(Update, update), cast(Any, None))

    chat_service.regenerate_last_response.assert_awaited_once()
    regenerate_kwargs = chat_service.regenerate_last_response.await_args.kwargs
    assert regenerate_kwargs["conversation_identity"] == ConversationIdentity.for_session(
        str(FIXED_SESSION_ID)
    )
    assert "processing_feedback" in regenerate_kwargs
    chat_service.send_message.assert_not_awaited()
    assert message.responses == ["regenerated"]


@pytest.mark.asyncio
async def test_regenerate_command_surfaces_specific_validation_error() -> None:
    chat_service = AsyncMock()
    chat_service.regenerate_last_response = AsyncMock(
        side_effect=ValueError("Conversation has no user message to regenerate from.")
    )
    adapter = TelegramAdapter(
        chat_service=chat_service,
        identity_resolver=FakeIdentityResolver(),
        group_identity_resolver=FakeGroupIdentityResolver(),
        character_service=FakeCharacterService(),
        authorization=TelegramAuthorization(set()),
        unauthorized_message="not authorized",
        message_max_length=3800,
    )

    message = FakeMessage(text="/regenerate")
    update = FakeUpdate(
        effective_message=message,
        effective_user=FakeUser(id=9),
        effective_chat=FakeChat(id=9, type="private"),
    )

    await adapter.handle_message(cast(Update, update), cast(Any, None))

    assert message.responses == ["Conversation has no user message to regenerate from."]


@pytest.mark.asyncio
async def test_clear_command_calls_clear_conversation_and_confirms() -> None:
    chat_service = AsyncMock()
    adapter = TelegramAdapter(
        chat_service=chat_service,
        identity_resolver=FakeIdentityResolver(),
        group_identity_resolver=FakeGroupIdentityResolver(),
        character_service=FakeCharacterService(),
        authorization=TelegramAuthorization(set()),
        unauthorized_message="not authorized",
        message_max_length=3800,
    )

    message = FakeMessage(text="/clear")
    update = FakeUpdate(
        effective_message=message,
        effective_user=FakeUser(id=10),
        effective_chat=FakeChat(id=-100, type="group"),
    )

    await adapter.handle_message(
        cast(Update, update),
        cast(Any, FakeContext(FakeBot(member_status="administrator"))),
    )

    chat_service.clear_conversation.assert_awaited_once_with(
        conversation_identity=ConversationIdentity.for_session(str(FIXED_SESSION_ID)),
    )
    assert message.responses == ["Conversation memory cleared."]


@pytest.mark.asyncio
async def test_unauthorized_user_gets_configured_message() -> None:
    chat_service = AsyncMock()
    adapter = TelegramAdapter(
        chat_service=chat_service,
        identity_resolver=FakeIdentityResolver(),
        group_identity_resolver=FakeGroupIdentityResolver(),
        character_service=FakeCharacterService(),
        authorization=TelegramAuthorization({"123"}),
        unauthorized_message="beta closed",
        message_max_length=3800,
    )

    message = FakeMessage(text="hello")
    update = FakeUpdate(
        effective_message=message,
        effective_user=FakeUser(id=999),
        effective_chat=FakeChat(id=999, type="private"),
    )

    await adapter.handle_message(cast(Update, update), cast(Any, None))

    assert message.responses == ["beta closed"]
    chat_service.send_message.assert_not_awaited()


@pytest.mark.asyncio
async def test_authorized_group_accepts_normal_messages() -> None:
    chat_service = AsyncMock()
    chat_service.send_message = AsyncMock(return_value="group reply")
    adapter = TelegramAdapter(
        chat_service=chat_service,
        identity_resolver=FakeIdentityResolver(),
        group_identity_resolver=FakeGroupIdentityResolver(),
        character_service=FakeCharacterService(),
        authorization=TelegramAuthorization(set(), {"-555"}),
        unauthorized_message="not authorized",
        message_max_length=3800,
    )

    message = FakeMessage(text="hello from group")
    update = FakeUpdate(
        effective_message=message,
        effective_user=FakeUser(id=77, username="alice", full_name="Alice"),
        effective_chat=FakeChat(id=-555, type="group"),
    )

    await adapter.handle_message(cast(Update, update), cast(Any, FakeContext(FakeBot())))

    chat_service.send_message.assert_awaited_once()
    send_kwargs = chat_service.send_message.await_args.kwargs
    assert send_kwargs["conversation_identity"] == ConversationIdentity.for_session(
        str(FIXED_SESSION_ID)
    )
    assert send_kwargs["message"] == "hello from group"
    assert send_kwargs["user_id"] == str(FIXED_USER_ID)
    assert send_kwargs["username"] == "alice"
    assert send_kwargs["display_name"] == "Alice"
    assert "processing_feedback" in send_kwargs
    assert message.responses == ["group reply"]


@pytest.mark.asyncio
async def test_unauthorized_group_gets_configured_message() -> None:
    chat_service = AsyncMock()
    adapter = TelegramAdapter(
        chat_service=chat_service,
        identity_resolver=FakeIdentityResolver(),
        group_identity_resolver=FakeGroupIdentityResolver(),
        character_service=FakeCharacterService(),
        authorization=TelegramAuthorization(set(), {"-123"}),
        unauthorized_message="group not allowed",
        message_max_length=3800,
    )

    message = FakeMessage(text="hello from group")
    update = FakeUpdate(
        effective_message=message,
        effective_user=FakeUser(id=77, username="alice", full_name="Alice"),
        effective_chat=FakeChat(id=-555, type="group"),
    )

    await adapter.handle_message(cast(Update, update), cast(Any, FakeContext(FakeBot())))

    chat_service.send_message.assert_not_awaited()
    assert message.responses == ["group not allowed"]


@pytest.mark.asyncio
async def test_group_chat_supported_command_still_works() -> None:
    chat_service = AsyncMock()
    chat_service.continue_story = AsyncMock(return_value="continued in group")
    adapter = TelegramAdapter(
        chat_service=chat_service,
        identity_resolver=FakeIdentityResolver(),
        group_identity_resolver=FakeGroupIdentityResolver(),
        character_service=FakeCharacterService(),
        authorization=TelegramAuthorization(set()),
        unauthorized_message="not authorized",
        message_max_length=3800,
    )

    message = FakeMessage(text="/continue")
    update = FakeUpdate(
        effective_message=message,
        effective_user=FakeUser(id=77),
        effective_chat=FakeChat(id=-555, type="group"),
    )

    await adapter.handle_message(
        cast(Update, update),
        cast(Any, FakeContext(FakeBot(member_status="administrator"))),
    )

    chat_service.continue_story.assert_awaited_once()
    continue_kwargs = chat_service.continue_story.await_args.kwargs
    assert continue_kwargs["conversation_identity"] == ConversationIdentity.for_session(
        str(FIXED_SESSION_ID)
    )
    assert "processing_feedback" in continue_kwargs
    assert message.responses == ["continued in group"]


@pytest.mark.asyncio
async def test_group_member_cannot_continue_or_clear() -> None:
    chat_service = AsyncMock()
    adapter = TelegramAdapter(
        chat_service=chat_service,
        identity_resolver=FakeIdentityResolver(),
        group_identity_resolver=FakeGroupIdentityResolver(),
        character_service=FakeCharacterService(),
        authorization=TelegramAuthorization(set(), {"-555"}),
        unauthorized_message="not authorized",
        message_max_length=3800,
    )

    continue_message = FakeMessage(text="/continue")
    continue_update = FakeUpdate(
        effective_message=continue_message,
        effective_user=FakeUser(id=77),
        effective_chat=FakeChat(id=-555, type="group"),
    )

    clear_message = FakeMessage(text="/clear")
    clear_update = FakeUpdate(
        effective_message=clear_message,
        effective_user=FakeUser(id=77),
        effective_chat=FakeChat(id=-555, type="group"),
    )

    context = cast(Any, FakeContext(FakeBot(member_status="member")))
    await adapter.handle_message(cast(Update, continue_update), context)
    await adapter.handle_message(cast(Update, clear_update), context)

    chat_service.continue_story.assert_not_awaited()
    chat_service.clear_conversation.assert_not_awaited()
    assert continue_message.responses == ["Only group administrators can use this command."]
    assert clear_message.responses == ["Only group administrators can use this command."]


@pytest.mark.asyncio
async def test_group_creator_can_clear() -> None:
    chat_service = AsyncMock()
    adapter = TelegramAdapter(
        chat_service=chat_service,
        identity_resolver=FakeIdentityResolver(),
        group_identity_resolver=FakeGroupIdentityResolver(),
        character_service=FakeCharacterService(),
        authorization=TelegramAuthorization(set(), {"-555"}),
        unauthorized_message="not authorized",
        message_max_length=3800,
    )

    message = FakeMessage(text="/clear")
    update = FakeUpdate(
        effective_message=message,
        effective_user=FakeUser(id=77),
        effective_chat=FakeChat(id=-555, type="group"),
    )

    await adapter.handle_message(
        cast(Update, update),
        cast(Any, FakeContext(FakeBot(member_status="creator"))),
    )

    chat_service.clear_conversation.assert_awaited_once_with(
        conversation_identity=ConversationIdentity.for_session(str(FIXED_SESSION_ID)),
    )
    assert message.responses == ["Conversation memory cleared."]


@pytest.mark.asyncio
async def test_long_response_is_split_and_delivered_in_multiple_messages() -> None:
    chat_service = AsyncMock()
    chat_service.send_message = AsyncMock(return_value="A" * 12)
    adapter = TelegramAdapter(
        chat_service=chat_service,
        identity_resolver=FakeIdentityResolver(),
        group_identity_resolver=FakeGroupIdentityResolver(),
        character_service=FakeCharacterService(),
        authorization=TelegramAuthorization(set()),
        unauthorized_message="not authorized",
        message_max_length=5,
    )

    message = FakeMessage(text="hello")
    update = FakeUpdate(
        effective_message=message,
        effective_user=FakeUser(id=42),
        effective_chat=FakeChat(id=42, type="private"),
    )

    await adapter.handle_message(cast(Update, update), cast(Any, None))

    assert message.responses == ["AAAAA", "AAAAA", "AA"]


@pytest.mark.asyncio
async def test_character_command_selects_active_character() -> None:
    chat_service = AsyncMock()
    adapter = TelegramAdapter(
        chat_service=chat_service,
        identity_resolver=FakeIdentityResolver(),
        group_identity_resolver=FakeGroupIdentityResolver(),
        character_service=FakeCharacterService(),
        authorization=TelegramAuthorization(set()),
        unauthorized_message="not authorized",
        message_max_length=3800,
    )

    message = FakeMessage(text="/character Belzebuth")
    update = FakeUpdate(
        effective_message=message,
        effective_user=FakeUser(id=42),
        effective_chat=FakeChat(id=42, type="private"),
    )

    await adapter.handle_message(cast(Update, update), cast(Any, None))

    assert message.responses == ["Active character set to 'belzebuth' in world 'default'."]
    chat_service.send_message.assert_not_awaited()
