from dataclasses import dataclass
from enum import StrEnum


class TelegramCommand(StrEnum):
    HELP = "/help"
    CONTINUE = "/continue"
    CLEAR = "/clear"
    CHARACTER = "/character"


@dataclass(frozen=True, slots=True)
class ParsedTransportMessage:
    text: str
    is_command: bool
    command: TelegramCommand | None
    argument: str | None
