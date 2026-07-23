from enum import StrEnum


class ScenarioVisibility(StrEnum):
    """Controls who may see and play a scenario.

    Access is evaluated per caller. Group callers are identified by their Telegram
    chat id; direct (individual) callers have no chat id and are treated as outsiders
    for RESTRICTED scenarios.
    """

    # Listed in /scenarios and playable by anyone.
    PUBLIC = "PUBLIC"
    # Not listed, but playable via /play <id> if the id is known (secret/unlisted).
    UNLISTED = "UNLISTED"
    # Listed and playable only for the allow-listed group chat ids; hidden from others.
    RESTRICTED = "RESTRICTED"
