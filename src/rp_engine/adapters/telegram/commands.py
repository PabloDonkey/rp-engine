from rp_engine.adapters.telegram.models import ParsedTransportMessage, TelegramCommand

SUPPORTED_COMMANDS: dict[str, TelegramCommand] = {
    TelegramCommand.START.value: TelegramCommand.START,
    TelegramCommand.HELP.value: TelegramCommand.HELP,
    TelegramCommand.BETA.value: TelegramCommand.BETA,
    TelegramCommand.CANCEL.value: TelegramCommand.CANCEL,
    TelegramCommand.SCENARIOS.value: TelegramCommand.SCENARIOS,
    TelegramCommand.PLAY.value: TelegramCommand.PLAY,
    TelegramCommand.CHAT.value: TelegramCommand.CHAT,
    TelegramCommand.CONTINUE.value: TelegramCommand.CONTINUE,
    TelegramCommand.RETRY.value: TelegramCommand.RETRY,
    TelegramCommand.RESTART.value: TelegramCommand.RESTART,
    TelegramCommand.ADMIN_BETA_LIST.value: TelegramCommand.ADMIN_BETA_LIST,
    TelegramCommand.ADMIN_BETA_ACCEPT.value: TelegramCommand.ADMIN_BETA_ACCEPT,
    TelegramCommand.ADMIN_BETA_REJECT.value: TelegramCommand.ADMIN_BETA_REJECT,
}

# Command menu shown to authorized players (set via set_my_commands).
TELEGRAM_MENU_COMMANDS: tuple[tuple[str, str], ...] = (
    ("start", "Resume your adventure or get started"),
    ("scenarios", "Browse available adventures"),
    ("play", "Start a scenario: /play <id>"),
    ("continue", "Let the story advance"),
    ("retry", "Regenerate the last narrator reply"),
    ("restart", "Restart the current adventure"),
    ("cancel", "Cancel the current menu"),
    ("help", "Show available commands"),
    ("beta", "Request a beta seat"),
)

UNAUTHORIZED_HELP_MESSAGE = (
    "RP Engine is in closed beta.\n\n"
    "Available commands:\n"
    "/start - Learn how to get access\n"
    "/beta - Request a beta seat\n"
    "/help - Show this help message"
)

AUTHORIZED_HELP_MESSAGE = (
    "Available commands:\n"
    "/start - Resume your adventure, or get started\n"
    "/scenarios - Browse available adventures\n"
    "/play <id> - Start a scenario\n"
    "/continue - Let the story advance without input\n"
    "/retry - Regenerate the last narrator reply\n"
    "/restart - Restart the current adventure from the beginning\n"
    "/cancel - Cancel the current menu\n"
    "/help - Show this help message\n"
    "/beta - Request a beta seat\n"
    "\nIn group chats, use /chat <message> to address the story."
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


def build_help_message(*, authorized: bool) -> str:
    return AUTHORIZED_HELP_MESSAGE if authorized else UNAUTHORIZED_HELP_MESSAGE
