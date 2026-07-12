from dataclasses import dataclass
from typing import Any, cast
from unittest.mock import AsyncMock
from uuid import UUID

import pytest
from telegram import Update

from rp_engine.adapters.telegram.adapter import TelegramAdapter
from rp_engine.adapters.telegram.authorization import TelegramAuthorization
from rp_engine.adapters.telegram.commands import HELP_MESSAGE
from rp_engine.core.memory.models import ConversationIdentity
from rp_engine.core.user.user import User

FIXED_USER_ID = UUID("00000000-0000-0000-0000-000000000042")


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

    chat_service.send_message.assert_awaited_once_with(
        conversation_identity=ConversationIdentity.for_private(str(FIXED_USER_ID)),
        message="hello",
        user_id=None,
        username=None,
        display_name=None,
    )
    assert message.responses == ["bot reply"]


@pytest.mark.asyncio
async def test_telegram_adapter_ignores_non_text_messages() -> None:
    chat_service = AsyncMock()
    adapter = TelegramAdapter(
        chat_service=chat_service,
        identity_resolver=FakeIdentityResolver(),
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

    chat_service.continue_story.assert_awaited_once_with(
        conversation_identity=ConversationIdentity.for_private(str(FIXED_USER_ID)),
    )
    chat_service.send_message.assert_not_awaited()
    assert message.responses == ["continued"]


@pytest.mark.asyncio
async def test_clear_command_calls_clear_conversation_and_confirms() -> None:
    chat_service = AsyncMock()
    adapter = TelegramAdapter(
        chat_service=chat_service,
        identity_resolver=FakeIdentityResolver(),
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
        conversation_identity=ConversationIdentity.for_group("-100"),
    )
    assert message.responses == ["Conversation memory cleared."]


@pytest.mark.asyncio
async def test_unauthorized_user_gets_configured_message() -> None:
    chat_service = AsyncMock()
    adapter = TelegramAdapter(
        chat_service=chat_service,
        identity_resolver=FakeIdentityResolver(),
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

    chat_service.send_message.assert_awaited_once_with(
        conversation_identity=ConversationIdentity.for_group("-555"),
        message="hello from group",
        user_id=str(FIXED_USER_ID),
        username="alice",
        display_name="Alice",
    )
    assert message.responses == ["group reply"]


@pytest.mark.asyncio
async def test_unauthorized_group_gets_configured_message() -> None:
    chat_service = AsyncMock()
    adapter = TelegramAdapter(
        chat_service=chat_service,
        identity_resolver=FakeIdentityResolver(),
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

    chat_service.continue_story.assert_awaited_once_with(
        conversation_identity=ConversationIdentity.for_group("-555"),
    )
    assert message.responses == ["continued in group"]


@pytest.mark.asyncio
async def test_group_member_cannot_continue_or_clear() -> None:
    chat_service = AsyncMock()
    adapter = TelegramAdapter(
        chat_service=chat_service,
        identity_resolver=FakeIdentityResolver(),
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
        conversation_identity=ConversationIdentity.for_group("-555"),
    )
    assert message.responses == ["Conversation memory cleared."]


@pytest.mark.asyncio
async def test_long_response_is_split_and_delivered_in_multiple_messages() -> None:
    chat_service = AsyncMock()
    chat_service.send_message = AsyncMock(return_value="A" * 12)
    adapter = TelegramAdapter(
        chat_service=chat_service,
        identity_resolver=FakeIdentityResolver(),
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
