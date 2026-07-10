import logging
from typing import Any

from telegram import Update
from telegram.ext import Application as TelegramApplication
from telegram.ext import ContextTypes, MessageHandler, filters

from rp_engine.core.services.chat_service import ChatService

logger = logging.getLogger(__name__)


class TelegramAdapter:
    def __init__(self, chat_service: ChatService) -> None:
        self._chat_service = chat_service

    async def handle_message(self, update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
        message = update.effective_message
        if message is None or message.text is None:
            return

        user = update.effective_user
        user_id = str(user.id) if user is not None else "anonymous"

        try:
            response = await self._chat_service.handle_user_message(
                user_id=user_id,
                message=message.text,
            )
        except ValueError:
            await message.reply_text("Please send a non-empty message.")
            return
        except Exception:
            logger.exception("Unexpected error while processing Telegram message")
            await message.reply_text("Sorry, I could not process your message right now.")
            return

        await message.reply_text(response)


class TelegramRuntime:
    def __init__(self, application: Any) -> None:
        self._application = application

    async def start(self) -> None:
        await self._application.initialize()
        await self._application.start()

        if self._application.updater is None:
            raise RuntimeError("Telegram updater is unavailable.")

        await self._application.updater.start_polling()

    async def stop(self) -> None:
        if self._application.updater is not None:
            await self._application.updater.stop()

        await self._application.stop()
        await self._application.shutdown()


def create_telegram_application(token: str, adapter: TelegramAdapter) -> Any:
    application = TelegramApplication.builder().token(token).build()
    handler = MessageHandler(filters.TEXT & ~filters.COMMAND, adapter.handle_message)
    application.add_handler(handler)
    return application
