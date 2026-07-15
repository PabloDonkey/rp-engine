from dataclasses import dataclass
from enum import StrEnum


class TelegramCommand(StrEnum):
    START = "/start"
    CHAT = "/chat"
    HELP = "/help"
    BETA = "/beta"
    CONTINUE = "/continue"
    REGENERATE = "/regenerate"
    CLEAR = "/clear"
    CHARACTER = "/character"


@dataclass(frozen=True, slots=True)
class ParsedTransportMessage:
    text: str
    is_command: bool
    command: TelegramCommand | None
    argument: str | None
