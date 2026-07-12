from rp_engine.adapters.telegram.invocation_policy import should_process_message
from rp_engine.adapters.telegram.models import ParsedTransportMessage, TelegramCommand


def test_private_chat_processes_normal_messages() -> None:
    parsed = ParsedTransportMessage(text="hello", is_command=False, command=None, argument=None)

    assert should_process_message("private", parsed) is True


def test_group_chat_ignores_normal_messages() -> None:
    parsed = ParsedTransportMessage(text="hello", is_command=False, command=None, argument=None)

    assert should_process_message("group", parsed) is True


def test_group_chat_processes_supported_commands() -> None:
    parsed = ParsedTransportMessage(
        text="/continue",
        is_command=True,
        command=TelegramCommand.CONTINUE,
        argument=None,
    )

    assert should_process_message("group", parsed) is True
