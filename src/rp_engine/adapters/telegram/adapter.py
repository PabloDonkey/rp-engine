import logging
from typing import Any

from telegram import Update
from telegram.ext import Application as TelegramApplication
from telegram.ext import ContextTypes, MessageHandler, filters

from rp_engine.adapters.telegram.authorization import TelegramAuthorization
from rp_engine.adapters.telegram.commands import build_help_message, parse_transport_message
from rp_engine.adapters.telegram.invocation_policy import should_process_message
from rp_engine.adapters.telegram.models import TelegramCommand
from rp_engine.core.memory.models import ConversationIdentity
from rp_engine.core.services.chat_service import ChatService

logger = logging.getLogger(__name__)


class TelegramAdapter:
    def __init__(
        self,
        chat_service: ChatService,
        authorization: TelegramAuthorization,
        unauthorized_message: str,
    ) -> None:
        self._chat_service = chat_service
        self._authorization = authorization
        self._unauthorized_message = unauthorized_message

    async def handle_message(self, update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
        message = update.effective_message
        if message is None or message.text is None:
            return

        user = update.effective_user
        user_id = str(user.id) if user is not None else "anonymous"
        conversation_identity = self._resolve_conversation_identity(update, user_id)
        if not self._authorization.is_authorized(user_id):
            logger.info("Telegram request denied", extra={"user_id": user_id})
            await message.reply_text(self._unauthorized_message)
            return

        parsed_message = parse_transport_message(message.text)
        chat_type = update.effective_chat.type if update.effective_chat is not None else None
        if not should_process_message(chat_type, parsed_message):
            return

        logger.info(
            "Telegram message received",
            extra={"memory_key": conversation_identity.to_memory_key().value},
        )

        try:
            if parsed_message.command == TelegramCommand.HELP:
                await message.reply_text(build_help_message())
                return

            if parsed_message.command == TelegramCommand.CONTINUE:
                response = await self._chat_service.continue_story(
                    conversation_identity=conversation_identity,
                )
                await message.reply_text(response)
                return

            if parsed_message.command == TelegramCommand.CLEAR:
                await self._chat_service.clear_conversation(
                    conversation_identity=conversation_identity,
                )
                await message.reply_text("Conversation cleared.")
                return

            if parsed_message.is_command:
                await message.reply_text(
                    "Unsupported command. Use /help to see available commands."
                )
                return

            response = await self._chat_service.send_message(
                conversation_identity=conversation_identity,
                message=parsed_message.text,
            )
        except ValueError:
            logger.warning(
                "Telegram failure",
                extra={"reason": "invalid_message", "user_id": user_id},
            )
            await message.reply_text("Please send a non-empty message.")
            return
        except Exception:
            logger.exception(
                "Telegram failure",
                extra={"reason": "unexpected_error", "user_id": user_id},
            )
            await message.reply_text("Sorry, I could not process your message right now.")
            return

        await message.reply_text(response)

    @staticmethod
    def _resolve_conversation_identity(update: Update, user_id: str) -> ConversationIdentity:
        chat = update.effective_chat
        if chat is None:
            return ConversationIdentity.for_private(user_id)

        if chat.type in {"group", "supergroup"}:
            return ConversationIdentity.for_group(str(chat.id))

        return ConversationIdentity.for_private(user_id)


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
