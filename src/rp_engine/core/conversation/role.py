from enum import StrEnum


class ConversationRole(StrEnum):
    SYSTEM = "system"
    USER = "user"
    CHARACTER = "character"