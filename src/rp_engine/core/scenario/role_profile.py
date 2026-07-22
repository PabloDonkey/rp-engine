from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class RoleProfile:
    """
    Abstract description of a role within a scenario.

    A role profile is independent of any concrete character. It describes what a
    participant in the scenario is expected to be and do (for example
    "protagonist", "narrator", "antagonist"). At runtime a ScenarioSession maps a
    concrete character onto each role via active_participants.

    Role profiles live in the scenario definition (the blueprint) and are reusable
    and immutable. They carry no runtime state.
    """

    id: str
    name: str
    description: str = ""
    objectives: tuple[str, ...] = ()
    constraints: tuple[str, ...] = ()
    metadata: dict[str, str] = field(default_factory=dict)
