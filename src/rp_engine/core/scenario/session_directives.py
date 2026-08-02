"""Player-set directives that steer a single scenario session.

Three controls share one value object because they share one lifecycle question —
*how long does this survive?* — and one destination, a dedicated system-prompt section:

| Directive | Lifetime |
|---|---|
| `language` | persistent, until changed |
| `rules` | persistent, until removed |
| `director_instructions` | one turn — the whole stack is cleared by the consuming generation |

The object is immutable like the rest of the domain; every mutator returns a new
instance. It is stored alongside its `ScenarioSession`, so directives never leak
between playthroughs.
"""

from dataclasses import dataclass, replace

# Sentinel language value meaning "let the model pick", i.e. emit no language section.
LANGUAGE_AUTO = "auto"

# Languages a player may request, mapped to the English name used in the prompt. Kept
# deliberately small: every entry is a promise that the model can hold a roleplay in it.
SUPPORTED_LANGUAGES: dict[str, str] = {
    LANGUAGE_AUTO: "Automatic",
    "en": "English",
    "es": "Spanish",
    "fr": "French",
    "de": "German",
    "it": "Italian",
    "pt": "Portuguese",
    "ru": "Russian",
    "ja": "Japanese",
    "zh": "Chinese",
}


def normalize_language(value: str) -> str | None:
    """Return the canonical language code for `value`, or None if unsupported."""
    candidate = value.strip().lower()
    if candidate in SUPPORTED_LANGUAGES:
        return candidate
    return None


def language_name(code: str) -> str:
    return SUPPORTED_LANGUAGES.get(code, code)


@dataclass(frozen=True, slots=True)
class ScenarioRule:
    """One persistent player-authored rule, addressable by a stable id."""

    id: str
    text: str


@dataclass(frozen=True, slots=True)
class SessionDirectives:
    language: str = LANGUAGE_AUTO
    rules: tuple[ScenarioRule, ...] = ()
    # A stack, not a slot: several `/director` notes can be queued before the next reply,
    # and they are consumed together by the generation that reads them.
    director_instructions: tuple[str, ...] = ()

    @property
    def has_language_preference(self) -> bool:
        return self.language != LANGUAGE_AUTO and self.language in SUPPORTED_LANGUAGES

    def with_language(self, code: str) -> "SessionDirectives":
        normalized = normalize_language(code)
        if normalized is None:
            raise ValueError(f"Unsupported language code: {code}")
        return replace(self, language=normalized)

    def with_rule(self, text: str) -> tuple["SessionDirectives", ScenarioRule]:
        """Append a rule, returning the new directives and the rule that was created."""
        cleaned = text.strip()
        if not cleaned:
            raise ValueError("Rule text must not be empty.")
        rule = ScenarioRule(id=self._next_rule_id(), text=cleaned)
        return replace(self, rules=(*self.rules, rule)), rule

    def without_rule(self, rule_id: str) -> "SessionDirectives | None":
        """Drop a rule by id, or return None when no rule carries that id."""
        target = rule_id.strip()
        remaining = tuple(rule for rule in self.rules if rule.id != target)
        if len(remaining) == len(self.rules):
            return None
        return replace(self, rules=remaining)

    @property
    def has_director_instructions(self) -> bool:
        return bool(self.director_instructions)

    def with_director_instruction(self, instruction: str) -> "SessionDirectives":
        """Queue another note for the next reply.

        Appends rather than replaces: a player sending two `/director` notes before the
        next turn means both, and the old single-slot version dropped all but the last
        without saying so.
        """
        cleaned = instruction.strip()
        if not cleaned:
            raise ValueError("Director instruction must not be empty.")
        return replace(self, director_instructions=(*self.director_instructions, cleaned))

    def without_director_instructions(self) -> "SessionDirectives":
        """Clear the whole queue — the notes share one turn, so they expire together."""
        return replace(self, director_instructions=())

    def _next_rule_id(self) -> str:
        """Ids are monotonic within a session and never reused, so a rule id a player
        read from `/rules` keeps pointing at the same rule after other rules are removed."""
        highest = 0
        for rule in self.rules:
            try:
                highest = max(highest, int(rule.id))
            except ValueError:
                continue
        return str(highest + 1)
