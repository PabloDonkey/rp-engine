from dataclasses import dataclass
from enum import StrEnum


class TelegramCommand(StrEnum):
    START = "/start"
    HELP = "/help"
    BETA = "/beta"
    CANCEL = "/cancel"
    SCENARIOS = "/scenarios"
    PLAY = "/play"
    CHAT = "/chat"
    CONTINUE = "/continue"
    RETRY = "/retry"
    RESTART = "/restart"
    ADMIN_BETA_LIST = "/admin_beta_list"
    ADMIN_BETA_ACCEPT = "/admin_beta_accept"
    ADMIN_BETA_REJECT = "/admin_beta_reject"


@dataclass(frozen=True, slots=True)
class ParsedTransportMessage:
    text: str
    is_command: bool
    command: TelegramCommand | None
    argument: str | None
