from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class GenerationSettings:
    temperature: float = 0.8
    max_tokens: int = 600
    top_p: float | None = None
    stop_sequences: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if self.max_tokens < 0:
            raise ValueError("max_tokens must be zero (unlimited) or greater.")
        if self.temperature < 0:
            raise ValueError("temperature must be greater than or equal to zero.")
        if self.top_p is not None and not 0 <= self.top_p <= 1:
            raise ValueError("top_p must be between 0 and 1.")
