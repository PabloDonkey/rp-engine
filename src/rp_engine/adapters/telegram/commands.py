from rp_engine.adapters.telegram.models import ParsedTransportMessage, TelegramCommand

SUPPORTED_COMMANDS: dict[str, TelegramCommand] = {
    TelegramCommand.HELP.value: TelegramCommand.HELP,
    TelegramCommand.CONTINUE.value: TelegramCommand.CONTINUE,
    TelegramCommand.REGENERATE.value: TelegramCommand.REGENERATE,
    TelegramCommand.CLEAR.value: TelegramCommand.CLEAR,
    TelegramCommand.CHARACTER.value: TelegramCommand.CHARACTER,
}

HELP_MESSAGE = (
    "Available commands:\n"
    "/help - Show this help message\n"
    "/continue - Continue the scene\n"
    "/regenerate - Replace the last character reply\n"
    "/clear - Clear the current conversation\n"
    "/character <name> - Select or create your active character"
)


def parse_transport_message(text: str) -> ParsedTransportMessage:
    cleaned = text.strip()
    if not cleaned:
        return ParsedTransportMessage(text="", is_command=False, command=None, argument=None)

    if not cleaned.startswith("/"):
        return ParsedTransportMessage(text=cleaned, is_command=False, command=None, argument=None)

    parts = cleaned.split(maxsplit=1)
    first_token = parts[0].lower()
    normalized = first_token.split("@", maxsplit=1)[0]
    command = SUPPORTED_COMMANDS.get(normalized)
    argument = parts[1].strip() if len(parts) > 1 else ""
    return ParsedTransportMessage(
        text=cleaned,
        is_command=True,
        command=command,
        argument=argument if argument else None,
    )


def build_help_message() -> str:
    return HELP_MESSAGE
