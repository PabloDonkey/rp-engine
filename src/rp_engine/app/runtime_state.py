from dataclasses import dataclass


@dataclass(slots=True)
class RuntimeState:
    app_state: str = "created"
