import asyncio
import json
import logging
import random
from collections import deque
from pathlib import Path
from typing import Any

from telegram.constants import ChatAction

from rp_engine.core.ports import FeedbackContext, NoOpProcessingFeedback, ProcessingFeedback

logger = logging.getLogger(__name__)

_DEFAULT_TYPING_REFRESH_SECONDS = 4.0
_DEFAULT_RECENT_HISTORY_SIZE = 3


class FeedbackTemplateSelector:
    def __init__(
        self,
        *,
        base_path: Path | str = "data",
        recent_history_size: int = _DEFAULT_RECENT_HISTORY_SIZE,
    ) -> None:
        self._base_path = Path(base_path)
        self._recent_history_size = max(1, recent_history_size)
        self._rng = random.Random()
        self._cache: dict[Path, list[str]] = {}
        self._recent_by_character: dict[str, deque[str]] = {}

    def select_message(self, *, context: FeedbackContext) -> str | None:
        templates = self._load_templates_for_character(context.character_id)
        if not templates:
            return None

        recent = self._recent_by_character.setdefault(
            context.character_id,
            deque(maxlen=self._recent_history_size),
        )
        choices = [template for template in templates if template not in recent]
        if not choices:
            recent.clear()
            choices = templates

        selected = self._rng.choice(choices)
        recent.append(selected)
        return self._render_template(selected, context=context)

    def _load_templates_for_character(self, character_id: str) -> list[str]:
        character_path = self._base_path / "characters" / character_id / "feedback_messages.json"
        character_default_path = (
            self._base_path / "characters" / "default" / "feedback_messages.json"
        )
        global_default_path = self._base_path / "feedback" / "default.json"

        for path in (character_path, character_default_path, global_default_path):
            templates = self._load_templates(path)
            if templates:
                return templates
        return []

    def _load_templates(self, path: Path) -> list[str]:
        cached = self._cache.get(path)
        if cached is not None:
            return cached

        if not path.exists():
            self._cache[path] = []
            return []

        try:
            with path.open("r", encoding="utf-8") as file:
                payload = json.load(file)
        except Exception:
            logger.exception("Failed to read feedback templates", extra={"path": str(path)})
            self._cache[path] = []
            return []

        if not isinstance(payload, list):
            self._cache[path] = []
            return []

        templates = [item.strip() for item in payload if isinstance(item, str) and item.strip()]
        self._cache[path] = templates
        return templates

    @staticmethod
    def _render_template(template: str, *, context: FeedbackContext) -> str:
        return (
            template.replace("{{char}}", context.character_name)
            .replace("{{user}}", context.user_display_name)
            .strip()
        )


class TelegramProcessingFeedback(ProcessingFeedback):
    def __init__(
        self,
        *,
        bot: Any,
        chat_id: int,
        source_message: Any,
        template_selector: FeedbackTemplateSelector,
        typing_refresh_seconds: float = _DEFAULT_TYPING_REFRESH_SECONDS,
    ) -> None:
        self._bot = bot
        self._chat_id = chat_id
        self._source_message = source_message
        self._template_selector = template_selector
        self._typing_refresh_seconds = max(0.5, typing_refresh_seconds)
        self._typing_task: asyncio.Task[None] | None = None
        self._stop_event = asyncio.Event()
        self._temporary_message: Any | None = None

    async def start(self, context: FeedbackContext) -> None:
        self._stop_event.clear()

        temporary_text = self._template_selector.select_message(context=context)
        if temporary_text:
            try:
                self._temporary_message = await self._source_message.reply_text(temporary_text)
            except Exception:
                logger.exception("Failed to send temporary processing message")

        self._typing_task = asyncio.create_task(self._typing_loop())

    async def update(self, message: str) -> None:
        if self._temporary_message is None:
            return

        if not message.strip():
            return

        edit_text = getattr(self._temporary_message, "edit_text", None)
        if edit_text is None:
            return

        try:
            await edit_text(message)
        except Exception:
            logger.exception("Failed to update temporary processing message")

    async def stop(self) -> None:
        self._stop_event.set()

        if self._typing_task is not None:
            self._typing_task.cancel()
            try:
                await self._typing_task
            except asyncio.CancelledError:
                pass
            finally:
                self._typing_task = None

        if self._temporary_message is not None:
            delete = getattr(self._temporary_message, "delete", None)
            if delete is not None:
                try:
                    await delete()
                except Exception:
                    logger.exception("Failed to delete temporary processing message")
            self._temporary_message = None

    async def _typing_loop(self) -> None:
        try:
            while not self._stop_event.is_set():
                await self._bot.send_chat_action(chat_id=self._chat_id, action=ChatAction.TYPING)
                try:
                    await asyncio.wait_for(
                        self._stop_event.wait(), timeout=self._typing_refresh_seconds
                    )
                except TimeoutError:
                    continue
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Typing loop failed")


class TelegramProcessingFeedbackFactory:
    def __init__(
        self,
        *,
        base_path: Path | str = "data",
        typing_refresh_seconds: float = _DEFAULT_TYPING_REFRESH_SECONDS,
    ) -> None:
        self._template_selector = FeedbackTemplateSelector(base_path=base_path)
        self._typing_refresh_seconds = typing_refresh_seconds

    def create(self, *, context: Any, source_message: Any) -> ProcessingFeedback:
        chat = getattr(source_message, "chat", None)
        bot = getattr(context, "bot", None) if context is not None else None
        chat_id = getattr(chat, "id", None)

        if bot is None or chat_id is None:
            return NoOpProcessingFeedback()

        return TelegramProcessingFeedback(
            bot=bot,
            chat_id=chat_id,
            source_message=source_message,
            template_selector=self._template_selector,
            typing_refresh_seconds=self._typing_refresh_seconds,
        )
