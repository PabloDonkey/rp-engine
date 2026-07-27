from dataclasses import dataclass, field
from typing import Literal

# Why the reply ended. `length` means the model hit its own output cap and the text can be
# usefully resumed; `context_length` means the context window filled, which resuming would
# only hit again — so the two are deliberately not merged.
FinishReason = Literal["stop", "length", "context_length", "unknown"]


@dataclass(frozen=True, slots=True)
class LLMResponse:
    content: str
    finish_reason: FinishReason = "stop"
    metadata: dict[str, str] = field(default_factory=dict)
    thinking: str | None = None
