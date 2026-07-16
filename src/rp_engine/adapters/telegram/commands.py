from rp_engine.adapters.telegram.models import ParsedTransportMessage, TelegramCommand

SUPPORTED_COMMANDS: dict[str, TelegramCommand] = {
    TelegramCommand.START.value: TelegramCommand.START,
    TelegramCommand.CHAT.value: TelegramCommand.CHAT,
    TelegramCommand.HELP.value: TelegramCommand.HELP,
    TelegramCommand.BETA.value: TelegramCommand.BETA,
    TelegramCommand.ADMIN_BETA_LIST.value: TelegramCommand.ADMIN_BETA_LIST,
    TelegramCommand.ADMIN_BETA_ACCEPT.value: TelegramCommand.ADMIN_BETA_ACCEPT,
    TelegramCommand.ADMIN_BETA_REJECT.value: TelegramCommand.ADMIN_BETA_REJECT,
    TelegramCommand.CONTINUE.value: TelegramCommand.CONTINUE,
    TelegramCommand.REGENERATE.value: TelegramCommand.REGENERATE,
    TelegramCommand.CLEAR.value: TelegramCommand.CLEAR,
    TelegramCommand.CHARACTER.value: TelegramCommand.CHARACTER,
}

TELEGRAM_MENU_COMMANDS: tuple[tuple[str, str], ...] = (
    ("start", "Show welcome message"),
    ("chat", "Send a message to the current character"),
    ("continue", "Continue the previous assistant reply"),
    ("regenerate", "Regenerate the last assistant reply"),
    ("clear", "Clear the current conversation"),
    ("beta", "Request a beta seat"),
)

HELP_MESSAGE = (
    "Available commands:\n"
    "/start - Show welcome and usage\n"
    "/chat <message> - Send a message to the character\n"
    "/help - Show this help message\n"
    "/beta - Request a beta seat\n"
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
