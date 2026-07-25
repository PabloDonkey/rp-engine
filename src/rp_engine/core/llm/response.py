from dataclasses import dataclass, field
from typing import Literal

FinishReason = Literal["stop", "length", "unknown"]


@dataclass(frozen=True, slots=True)
class LLMResponse:
    content: str
    finish_reason: FinishReason = "stop"
    metadata: dict[str, str] = field(default_factory=dict)
    thinking: str | None = None
