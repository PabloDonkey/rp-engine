"""The player's own character within a scenario session.

A persona is two pieces of free text — a **name**, which is what `{{user}}` resolves to
for the rest of the playthrough, and an optional **description** the prompt renders as a
`[User Persona]` section. Both are captured once, when a genuinely new session starts,
and are immutable for that session's life (see ADR-025): `/restart` carries them forward,
`/clear` starts a new session without them and asks again.

The wire format is deliberately dumb so a player can type it in one message without
learning a syntax: **the first line is the name, everything after it is the description.**
That rule is the persona's own contract rather than Telegram's, so it lives here and any
future transport parses the same way.
"""


def parse_persona_reply(text: str) -> tuple[str, str]:
    """Split a free-text persona reply into `(name, description)`.

    Raises `ValueError` when no non-blank first line is present. A blank reply is *not*
    silently treated as "skip" — skipping is an explicit command at the transport, so the
    parse never has to guess what a short or empty message meant.
    """
    name, _, description = text.strip().partition("\n")
    cleaned_name = name.strip()
    if not cleaned_name:
        raise ValueError("A persona needs a name on the first line.")
    return cleaned_name, description.strip()
