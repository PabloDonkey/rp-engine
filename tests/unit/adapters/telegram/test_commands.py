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


def test_parse_transport_message_for_chat_command_argument() -> None:
    parsed = parse_transport_message("/chat hello from group")

    assert parsed.is_command is True
    assert parsed.command == TelegramCommand.CHAT
    assert parsed.argument == "hello from group"


def test_parse_transport_message_for_start_command() -> None:
    parsed = parse_transport_message("/start")

    assert parsed.is_command is True
    assert parsed.command == TelegramCommand.START
    assert parsed.argument is None


def test_parse_transport_message_for_beta_command() -> None:
    parsed = parse_transport_message("/beta")

    assert parsed.is_command is True
    assert parsed.command == TelegramCommand.BETA
    assert parsed.argument is None


def test_parse_transport_message_for_cancel_command() -> None:
    parsed = parse_transport_message("/cancel")

    assert parsed.is_command is True
    assert parsed.command == TelegramCommand.CANCEL
    assert parsed.argument is None


def test_parse_transport_message_for_retry_command() -> None:
    parsed = parse_transport_message("/retry")

    assert parsed.is_command is True
    assert parsed.command == TelegramCommand.RETRY
    assert parsed.argument is None


def test_parse_transport_message_for_unsupported_command() -> None:
    parsed = parse_transport_message("/unknown")

    assert parsed.is_command is True
    assert parsed.command is None
    assert parsed.argument is None


def test_parse_transport_message_for_play_command_argument() -> None:
    parsed = parse_transport_message("/play sealed-vault")

    assert parsed.command == TelegramCommand.PLAY
    assert parsed.argument == "sealed-vault"


def test_parse_transport_message_for_scenarios_command() -> None:
    parsed = parse_transport_message("/scenarios")

    assert parsed.command == TelegramCommand.SCENARIOS
    assert parsed.argument is None


def test_removed_commands_are_unsupported() -> None:
    for text in ("/character Belzebuth", "/regenerate", "/clear"):
        parsed = parse_transport_message(text)
        assert parsed.is_command is True
        assert parsed.command is None


def test_parse_transport_message_for_admin_accept_command_argument() -> None:
    parsed = parse_transport_message("/admin_beta_accept 123456")

    assert parsed.command == TelegramCommand.ADMIN_BETA_ACCEPT
    assert parsed.argument == "123456"


def test_build_help_message_is_authorization_aware() -> None:
    authorized = build_help_message(authorized=True)
    assert "/start" in authorized
    assert "/scenarios" in authorized
    assert "/play" in authorized
    assert "/continue" in authorized
    assert "/retry" in authorized
    assert "/restart" in authorized
    assert "/character" not in authorized
    assert "/clear" not in authorized
    assert "/admin_beta_list" not in authorized

    unauthorized = build_help_message(authorized=False)
    assert "/beta" in unauthorized
    assert "/scenarios" not in unauthorized
    assert "/play" not in unauthorized


def test_parse_transport_message_for_director_command() -> None:
    parsed = parse_transport_message("/director introduce a stranger")

    assert parsed.command == TelegramCommand.DIRECTOR
    assert parsed.argument == "introduce a stranger"


def test_parse_transport_message_for_rule_subcommand() -> None:
    parsed = parse_transport_message("/rule add keep replies short")

    assert parsed.command == TelegramCommand.RULE
    assert parsed.argument == "add keep replies short"


def test_parse_transport_message_distinguishes_rule_from_rules() -> None:
    assert parse_transport_message("/rules").command == TelegramCommand.RULES
    assert parse_transport_message("/rule").command == TelegramCommand.RULE


def test_parse_transport_message_for_language_command() -> None:
    parsed = parse_transport_message("/language@rp_engine_bot fr")

    assert parsed.command == TelegramCommand.LANGUAGE
    assert parsed.argument == "fr"


def test_authorized_help_documents_the_directive_commands() -> None:
    help_text = build_help_message(authorized=True)

    assert "/director" in help_text
    assert "/rule add" in help_text
    assert "/rules" in help_text
    assert "/language" in help_text
