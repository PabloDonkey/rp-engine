from dataclasses import dataclass
from unittest.mock import AsyncMock

import pytest

from rp_engine.adapters.telegram.adapter import TelegramRuntime


@dataclass
class FakeUpdater:
    start_polling: AsyncMock
    stop: AsyncMock


@dataclass
class FakeBot:
    set_my_commands: AsyncMock


class FakeApplication:
    def __init__(self) -> None:
        self.initialize = AsyncMock()
        self.start = AsyncMock()
        self.stop = AsyncMock()
        self.shutdown = AsyncMock()
        self.bot = FakeBot(set_my_commands=AsyncMock())
        self.updater = FakeUpdater(start_polling=AsyncMock(), stop=AsyncMock())


@pytest.mark.asyncio
async def test_telegram_runtime_registers_command_menu_on_start() -> None:
    application = FakeApplication()
    runtime = TelegramRuntime(application=application)

    await runtime.start()

    application.initialize.assert_awaited_once()
    application.bot.set_my_commands.assert_awaited_once()

    await_args = application.bot.set_my_commands.await_args
    assert await_args is not None
    commands = await_args.args[0]
    command_names = [command.command for command in commands]
    assert command_names == [
        "start",
        "scenarios",
        "play",
        "continue",
        "retry",
        "restart",
        "clear",
        "director",
        "rules",
        "rule",
        "language",
        "memory",
        "cancel",
        "help",
        "beta",
    ]
    assert "chat" not in command_names
    assert "character" not in command_names
    assert "admin_beta_list" not in command_names
    assert "admin_beta_accept" not in command_names
    assert "admin_beta_reject" not in command_names


@pytest.mark.asyncio
async def test_telegram_runtime_stop_stops_updater_and_application() -> None:
    application = FakeApplication()
    runtime = TelegramRuntime(application=application)

    await runtime.stop()

    application.updater.stop.assert_awaited_once()
    application.stop.assert_awaited_once()
    application.shutdown.assert_awaited_once()
