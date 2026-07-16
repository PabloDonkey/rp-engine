from dataclasses import dataclass
from enum import StrEnum


class TelegramCommand(StrEnum):
    START = "/start"
    CHAT = "/chat"
    HELP = "/help"
    BETA = "/beta"
    ADMIN_BETA_LIST = "/admin_beta_list"
    ADMIN_BETA_ACCEPT = "/admin_beta_accept"
    ADMIN_BETA_REJECT = "/admin_beta_reject"
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
