from rp_engine.adapters.telegram.models import ParsedTransportMessage, TelegramCommand

SUPPORTED_COMMANDS: dict[str, TelegramCommand] = {
    TelegramCommand.HELP.value: TelegramCommand.HELP,
    TelegramCommand.CONTINUE.value: TelegramCommand.CONTINUE,
    TelegramCommand.CLEAR.value: TelegramCommand.CLEAR,
}

HELP_MESSAGE = (
    "Available commands:\n"
    "/help - Show this help message\n"
    "/continue - Continue the scene\n"
    "/clear - Clear the current conversation"
)


def parse_transport_message(text: str) -> ParsedTransportMessage:
    cleaned = text.strip()
    if not cleaned:
        return ParsedTransportMessage(text="", is_command=False, command=None)

    if not cleaned.startswith("/"):
        return ParsedTransportMessage(text=cleaned, is_command=False, command=None)

    first_token = cleaned.split(maxsplit=1)[0].lower()
    normalized = first_token.split("@", maxsplit=1)[0]
    command = SUPPORTED_COMMANDS.get(normalized)
    return ParsedTransportMessage(text=cleaned, is_command=True, command=command)


def build_help_message() -> str:
    return HELP_MESSAGE
