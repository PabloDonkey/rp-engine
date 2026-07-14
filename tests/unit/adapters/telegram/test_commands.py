from rp_engine.adapters.telegram.commands import build_help_message, parse_transport_message
from rp_engine.adapters.telegram.models import TelegramCommand


def test_parse_transport_message_for_plain_text() -> None:
    parsed = parse_transport_message(" hello world ")

    assert parsed.text == "hello world"
    assert parsed.is_command is False
    assert parsed.command is None
    assert parsed.argument is None


def test_parse_transport_message_for_supported_command_with_bot_mention() -> None:
    parsed = parse_transport_message("/continue@rp_engine_bot now")

    assert parsed.is_command is True
    assert parsed.command == TelegramCommand.CONTINUE
    assert parsed.argument == "now"


def test_parse_transport_message_for_regenerate_command() -> None:
    parsed = parse_transport_message("/regenerate")

    assert parsed.is_command is True
    assert parsed.command == TelegramCommand.REGENERATE
    assert parsed.argument is None


def test_parse_transport_message_for_unsupported_command() -> None:
    parsed = parse_transport_message("/unknown")

    assert parsed.is_command is True
    assert parsed.command is None
    assert parsed.argument is None


def test_parse_transport_message_for_character_command_argument() -> None:
    parsed = parse_transport_message("/character Belzebuth")

    assert parsed.command == TelegramCommand.CHARACTER
    assert parsed.argument == "Belzebuth"


def test_build_help_message_lists_supported_commands() -> None:
    help_message = build_help_message()

    assert "/help" in help_message
    assert "/continue" in help_message
    assert "/clear" in help_message
    assert "/regenerate" in help_message
    assert "/character" in help_message
