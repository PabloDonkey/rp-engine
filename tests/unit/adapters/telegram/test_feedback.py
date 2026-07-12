import asyncio
from dataclasses import dataclass
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from rp_engine.adapters.telegram.feedback import (
    FeedbackTemplateSelector,
    TelegramProcessingFeedback,
)
from rp_engine.core.ports import FeedbackContext


@dataclass
class FakeChat:
    id: int


class FakeTemporaryMessage:
    def __init__(self) -> None:
        self.delete = AsyncMock()
        self.edit_text = AsyncMock()


class FakeSourceMessage:
    def __init__(self) -> None:
        self.chat = FakeChat(id=101)
        self.reply_text = AsyncMock()
        self.temporary_message = FakeTemporaryMessage()
        self.reply_text.return_value = self.temporary_message


def test_feedback_selector_prefers_character_templates(tmp_path: Path) -> None:
    character_dir = tmp_path / "characters" / "tord"
    character_dir.mkdir(parents=True, exist_ok=True)
    (character_dir / "feedback_messages.json").write_text(
        '["{{char}} is watching {{user}}..."]',
        encoding="utf-8",
    )

    selector = FeedbackTemplateSelector(base_path=tmp_path)
    selected = selector.select_message(
        context=FeedbackContext(
            conversation_owner_id="session-1",
            character_id="tord",
            character_name="Tord",
            user_display_name="Pablo",
            world_id="default",
        )
    )

    assert selected == "Tord is watching Pablo..."


def test_feedback_selector_falls_back_to_global_default(tmp_path: Path) -> None:
    feedback_dir = tmp_path / "feedback"
    feedback_dir.mkdir(parents=True, exist_ok=True)
    (feedback_dir / "default.json").write_text(
        '["{{char}} is thinking..."]',
        encoding="utf-8",
    )

    selector = FeedbackTemplateSelector(base_path=tmp_path)
    selected = selector.select_message(
        context=FeedbackContext(
            conversation_owner_id="session-2",
            character_id="unknown",
            character_name="Belzebuth",
            user_display_name="Pablo",
            world_id="default",
        )
    )

    assert selected == "Belzebuth is thinking..."


@pytest.mark.asyncio
async def test_telegram_processing_feedback_start_and_stop_cleanup(tmp_path: Path) -> None:
    character_dir = tmp_path / "characters" / "tord"
    character_dir.mkdir(parents=True, exist_ok=True)
    (character_dir / "feedback_messages.json").write_text(
        '["{{char}} is deciding what to say..."]',
        encoding="utf-8",
    )

    selector = FeedbackTemplateSelector(base_path=tmp_path)
    source_message = FakeSourceMessage()
    bot = AsyncMock()
    bot.send_chat_action = AsyncMock()

    feedback = TelegramProcessingFeedback(
        bot=bot,
        chat_id=101,
        source_message=source_message,
        template_selector=selector,
        typing_refresh_seconds=0.5,
    )
    context = FeedbackContext(
        conversation_owner_id="session-3",
        character_id="tord",
        character_name="Tord",
        user_display_name="Pablo",
        world_id="default",
    )

    await feedback.start(context)
    await asyncio.sleep(0.01)
    await feedback.stop()

    source_message.reply_text.assert_awaited_once_with("Tord is deciding what to say...")
    source_message.temporary_message.delete.assert_awaited_once()
    assert bot.send_chat_action.await_count >= 1
