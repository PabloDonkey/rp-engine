from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class GenerationRequest:
    user_id: str
    message: str


@dataclass(frozen=True, slots=True)
class PromptPayload:
    system_prompt: str
    user_message: str
