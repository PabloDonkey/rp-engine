import logging
from typing import Any, Protocol

from telegram import Update
from telegram.ext import Application as TelegramApplication
from telegram.ext import ContextTypes, MessageHandler, filters

from rp_engine.adapters.telegram.authorization import TelegramAuthorization
from rp_engine.adapters.telegram.commands import build_help_message, parse_transport_message
from rp_engine.adapters.telegram.feedback import TelegramProcessingFeedbackFactory
from rp_engine.adapters.telegram.invocation_policy import should_process_message
from rp_engine.adapters.telegram.models import TelegramCommand
from rp_engine.adapters.telegram.splitter import split_message
from rp_engine.core.group.group import Group
from rp_engine.core.memory.models import ConversationIdentity
from rp_engine.core.services.chat_service import ChatService
from rp_engine.core.services.commands import SelectCharacterCommand
from rp_engine.core.session.session import Session
from rp_engine.core.user.user import User

logger = logging.getLogger(__name__)


class IdentityResolverPort(Protocol):
    async def resolve_identity(
        self,
        *,
        provider: str,
        external_id: str,
        display_name: str,
        metadata: dict[str, str] | None = None,
    ) -> User: ...


class CharacterServicePort(Protocol):
    async def select_character_for_user(
        self,
        *,
        user_id: Any,
        command: SelectCharacterCommand,
    ) -> Session: ...

    async def select_character_for_group(
        self,
        *,
        group_id: Any,
        command: SelectCharacterCommand,
    ) -> Session: ...

    async def ensure_active_session_for_user(self, *, user_id: Any) -> Session: ...

    async def ensure_active_session_for_group(self, *, group_id: Any) -> Session: ...


class GroupIdentityResolverPort(Protocol):
    async def resolve_identity(
        self,
        *,
        provider: str,
        external_id: str,
        display_name: str,
        metadata: dict[str, str] | None = None,
    ) -> Group: ...


class TelegramAdapter:
    def __init__(
        self,
        chat_service: ChatService,
        identity_resolver: IdentityResolverPort,
        group_identity_resolver: GroupIdentityResolverPort,
        character_service: CharacterServicePort,
        authorization: TelegramAuthorization,
        unauthorized_message: str,
        message_max_length: int,
        processing_feedback_factory: TelegramProcessingFeedbackFactory | None = None,
    ) -> None:
        self._chat_service = chat_service
        self._identity_resolver = identity_resolver
        self._group_identity_resolver = group_identity_resolver
        self._character_service = character_service
        self._authorization = authorization
        self._unauthorized_message = unauthorized_message
        self._message_max_length = message_max_length
        self._processing_feedback_factory = (
            processing_feedback_factory or TelegramProcessingFeedbackFactory()
        )

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        message = update.effective_message
        if message is None or message.text is None:
            return

        user = update.effective_user
        user_id = str(user.id) if user is not None else "anonymous"
        chat = update.effective_chat
        chat_type = chat.type if chat is not None else None

        if not self._is_authorized(chat_type=chat_type, user_id=user_id, chat=chat):
            logger.info(
                "Telegram request denied",
                extra={"user_id": user_id, "chat_type": chat_type},
            )
            await self._reply_with_split(message=message, text=self._unauthorized_message)
            return

        resolved_user = await self._identity_resolver.resolve_identity(
            provider="telegram",
            external_id=user_id,
            display_name=user.full_name if user is not None else "Anonymous",
            metadata={
                "username": user.username or "",
                "first_name": user.first_name or "",
                "last_name": user.last_name or "",
            }
            if user is not None
            else {},
        )

        parsed_message = parse_transport_message(message.text)
        if not should_process_message(chat_type, parsed_message):
            return

        is_group_chat = chat_type in {"group", "supergroup"}
        resolved_group: Group | None = None
        if is_group_chat:
            group_external_id = str(chat.id) if chat is not None else ""
            resolved_group = await self._group_identity_resolver.resolve_identity(
                provider="telegram",
                external_id=group_external_id,
                display_name=self._resolve_group_display_name(chat=chat),
                metadata={"chat_type": chat_type or "unknown"},
            )

        if parsed_message.command == TelegramCommand.CHARACTER:
            character_name = parsed_message.argument
            if character_name is None:
                await self._reply_with_split(
                    message=message,
                    text="Usage: /character <name>",
                )
                return

            try:
                if resolved_group is None:
                    selected_session = await self._character_service.select_character_for_user(
                        user_id=resolved_user.id,
                        command=SelectCharacterCommand(character_name=character_name),
                    )
                else:
                    selected_session = await self._character_service.select_character_for_group(
                        group_id=resolved_group.id,
                        command=SelectCharacterCommand(character_name=character_name),
                    )
            except ValueError as exc:
                await self._reply_with_split(message=message, text=str(exc))
                return

            await self._reply_with_split(
                message=message,
                text=(
                    f"Active character set to '{selected_session.character_id}' in "
                    f"world '{selected_session.world_id}'."
                ),
            )
            return

        if resolved_group is None:
            active_session = await self._character_service.ensure_active_session_for_user(
                user_id=resolved_user.id
            )
        else:
            active_session = await self._character_service.ensure_active_session_for_group(
                group_id=resolved_group.id
            )
        conversation_identity = ConversationIdentity.for_session(str(active_session.id))

        logger.info(
            "Telegram message received",
            extra={"memory_key": conversation_identity.to_memory_key().value},
        )

        group_user_id = str(resolved_user.id) if is_group_chat else None
        group_username = user.username if user is not None and is_group_chat else None
        group_display_name = user.full_name if user is not None and is_group_chat else None

        try:
            if parsed_message.command == TelegramCommand.HELP:
                await self._reply_with_split(message=message, text=build_help_message())
                return

            if parsed_message.command == TelegramCommand.CONTINUE:
                if chat_type in {"group", "supergroup"} and not await self._is_group_admin(
                    context=context,
                    update=update,
                ):
                    await self._reply_with_split(
                        message=message,
                        text="Only group administrators can use this command.",
                    )
                    return
                response = await self._chat_service.continue_story(
                    conversation_identity=conversation_identity,
                    processing_feedback=self._processing_feedback_factory.create(
                        context=context,
                        source_message=message,
                    ),
                )
                await self._reply_with_split(message=message, text=response)
                return

            if parsed_message.command == TelegramCommand.CLEAR:
                if chat_type in {"group", "supergroup"} and not await self._is_group_admin(
                    context=context,
                    update=update,
                ):
                    await self._reply_with_split(
                        message=message,
                        text="Only group administrators can use this command.",
                    )
                    return
                await self._chat_service.clear_conversation(
                    conversation_identity=conversation_identity,
                )
                await self._reply_with_split(message=message, text="Conversation memory cleared.")
                return

            if parsed_message.is_command:
                await self._reply_with_split(
                    message=message,
                    text="Unsupported command. Use /help to see available commands.",
                )
                return

            response = await self._chat_service.send_message(
                conversation_identity=conversation_identity,
                message=parsed_message.text,
                user_id=group_user_id,
                username=group_username,
                display_name=group_display_name,
                processing_feedback=self._processing_feedback_factory.create(
                    context=context,
                    source_message=message,
                ),
            )
        except ValueError:
            logger.warning(
                "Telegram failure",
                extra={"reason": "invalid_message", "user_id": user_id},
            )
            await self._reply_with_split(message=message, text="Please send a non-empty message.")
            return
        except Exception:
            logger.exception(
                "Telegram failure",
                extra={"reason": "unexpected_error", "user_id": user_id},
            )
            await self._reply_with_split(
                message=message,
                text="Sorry, I could not process your message right now.",
            )
            return

        await self._reply_with_split(message=message, text=response)

    def _is_authorized(self, *, chat_type: str | None, user_id: str, chat: Any) -> bool:
        if chat_type in {"group", "supergroup"}:
            group_id = str(chat.id) if chat is not None else ""
            return self._authorization.is_group_chat_authorized(group_id)
        return self._authorization.is_private_chat_authorized(user_id)

    async def _is_group_admin(
        self,
        *,
        context: ContextTypes.DEFAULT_TYPE,
        update: Update,
    ) -> bool:
        chat = update.effective_chat
        user = update.effective_user
        if chat is None or user is None:
            return False

        member = await context.bot.get_chat_member(chat_id=chat.id, user_id=user.id)
        return member.status in {"administrator", "creator"}

    async def _reply_with_split(self, *, message: Any, text: str) -> None:
        chunks = split_message(text, self._message_max_length)
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug(
                "Telegram message split",
                extra={
                    "characters": len(text),
                    "chunks": len(chunks),
                    "chunk_sizes": [len(chunk) for chunk in chunks],
                },
            )

        for chunk in chunks:
            await message.reply_text(chunk)

    @staticmethod
    def _resolve_group_display_name(*, chat: Any) -> str:
        if chat is not None:
            title = getattr(chat, "title", None)
            if isinstance(title, str) and title.strip():
                return title.strip()
            chat_id = getattr(chat, "id", None)
            if chat_id is not None:
                return f"Group {chat_id}"
        return "Group"


class TelegramRuntime:
    def __init__(self, application: Any) -> None:
        self._application = application

    async def start(self) -> None:
        logger.info("Starting Telegram runtime")
        await self._application.initialize()
        await self._application.start()

        if self._application.updater is None:
            raise RuntimeError("Telegram updater is unavailable.")

        await self._application.updater.start_polling()
        logger.info("Telegram polling started")

    async def stop(self) -> None:
        logger.info("Stopping Telegram runtime")
        if self._application.updater is not None:
            await self._application.updater.stop()

        await self._application.stop()
        await self._application.shutdown()


def create_telegram_application(token: str, adapter: TelegramAdapter) -> Any:
    application = TelegramApplication.builder().token(token).build()
    handler = MessageHandler(filters.TEXT, adapter.handle_message)
    application.add_handler(handler)
    return application
