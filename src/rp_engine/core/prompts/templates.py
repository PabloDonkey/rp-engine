"""Placeholder substitution for scenario-authored text.

Scenario cards are written with `{{char}}`, `{{user}}` and `{{world}}` placeholders. They
are resolved in two places — the prompt the model sees, and the scenario text a transport
echoes back to the player (the opening line, a resumed narration) — so the rule lives here
rather than in either caller, and a player never reads a raw placeholder the model saw
filled in.
"""

# What `{{char}}` falls back to in a characterless (freeform) scenario.
DEFAULT_CHARACTER_NAME = "the character"


def resolve_templates(
    value: str,
    *,
    user_name: str,
    character_name: str = "",
    world_name: str = "",
) -> str:
    return (
        value.replace("{{char}}", character_name or DEFAULT_CHARACTER_NAME)
        .replace("{{user}}", user_name)
        .replace("{{world}}", world_name)
        .strip()
    )
