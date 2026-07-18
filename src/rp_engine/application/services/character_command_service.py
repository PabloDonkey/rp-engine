from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass
from enum import Enum
from uuid import UUID

from rp_engine.core.character.character import Character
from rp_engine.core.character.visibility import CharacterVisibility
from rp_engine.core.ports.character_store import CharacterStore


class CreationStep(Enum):
    WAITING_FOR_NAME = "waiting_for_name"
    WAITING_FOR_DESCRIPTION = "waiting_for_description"
    WAITING_FOR_PERSONALITY = "waiting_for_personality"
    WAITING_FOR_SCENARIO = "waiting_for_scenario"
    WAITING_FOR_FIRST_MESSAGE = "waiting_for_first_message"


class EditStep(Enum):
    WAITING_FOR_FIELD_SELECTION = "waiting_for_field_selection"
    WAITING_FOR_FIELD_VALUE = "waiting_for_field_value"


class EditableField(Enum):
    NAME = "name"
    DESCRIPTION = "description"
    PERSONALITY = "personality"
    SCENARIO = "scenario"
    FIRST_MESSAGE = "first_message"


@dataclass(slots=True)
class CreationWorkflowState:
    step: CreationStep
    name: str = ""
    description: str = ""
    personality: str = ""
    scenario: str = ""
    first_message: str = ""


@dataclass(slots=True)
class EditWorkflowState:
    step: EditStep
    character_id: str
    selected_field: EditableField | None = None


@dataclass(slots=True)
class WorkflowResponse:
    message: str
    completed: bool = False


@dataclass(frozen=True, slots=True)
class CharacterCardData:
    name: str
    description: str
    personality: str
    scenario: str
    first_message: str


class CharacterCommandService:
    def __init__(self, *, character_store: CharacterStore) -> None:
        self._character_store = character_store
        self._lock = asyncio.Lock()
        self._creation_workflows: dict[UUID, CreationWorkflowState] = {}
        self._edit_workflows: dict[UUID, EditWorkflowState] = {}

    async def start_creation(self, *, user_id: UUID) -> WorkflowResponse:
        async with self._lock:
            conflict = self._ensure_no_active_workflow(user_id=user_id)
            if conflict is not None:
                return WorkflowResponse(message=conflict)
            self._creation_workflows[user_id] = CreationWorkflowState(
                step=CreationStep.WAITING_FOR_NAME
            )
        return WorkflowResponse(message="What is the character name?")

    async def start_edit(self, *, user_id: UUID, character_name: str) -> WorkflowResponse:
        name = character_name.strip()
        if not name:
            return WorkflowResponse(message="Usage: /character edit <character>")

        async with self._lock:
            conflict = self._ensure_no_active_workflow(user_id=user_id)
            if conflict is not None:
                return WorkflowResponse(message=conflict)

            character = await self._find_owned_character(user_id=user_id, name_or_id=name)
            if character is None:
                return WorkflowResponse(
                    message=(
                        "You can only edit characters that you own, and this character "
                        "was not found."
                    )
                )

            self._edit_workflows[user_id] = EditWorkflowState(
                step=EditStep.WAITING_FOR_FIELD_SELECTION,
                character_id=character.id,
            )

        return WorkflowResponse(message=self._build_edit_selection_prompt())

    async def show_character(self, *, user_id: UUID, character_name: str) -> WorkflowResponse:
        name = character_name.strip()
        if not name:
            return WorkflowResponse(message="Usage: /character show <character>")

        character = await self._find_owned_character(user_id=user_id, name_or_id=name)
        if character is None:
            return WorkflowResponse(message="Character not found for your account.")

        scenario = character.metadata.get("scenario", "")
        lines = [
            "Character summary",
            f"Name: {character.name}",
            f"Description: {character.description}",
            f"Personality: {character.personality}",
            f"Scenario: {scenario}",
            f"First message: {character.greeting}",
        ]
        return WorkflowResponse(message="\n".join(lines), completed=True)

    async def validate_character(self, *, user_id: UUID, character_name: str) -> WorkflowResponse:
        name = character_name.strip()
        if not name:
            return WorkflowResponse(message="Usage: /character validate <character>")

        character = await self._find_owned_character(user_id=user_id, name_or_id=name)
        if character is None:
            return WorkflowResponse(message="Character not found for your account.")

        data = self._to_card_data(character)
        errors = self._validate_card_data(data)
        if errors:
            return WorkflowResponse(
                message="Validation failed:\n" + "\n".join(f"- {error}" for error in errors),
                completed=True,
            )

        return WorkflowResponse(
            message="Character is valid for required Character Card v3 fields.",
            completed=True,
        )

    async def cancel(self, *, user_id: UUID) -> WorkflowResponse:
        async with self._lock:
            had_creation = self._creation_workflows.pop(user_id, None) is not None
            had_edit = self._edit_workflows.pop(user_id, None) is not None
        if had_creation or had_edit:
            return WorkflowResponse(message="Current operation cancelled.", completed=True)
        return WorkflowResponse(message="No active operation to cancel.", completed=True)

    async def has_active_workflow(self, *, user_id: UUID) -> bool:
        async with self._lock:
            return user_id in self._creation_workflows or user_id in self._edit_workflows

    async def handle_user_input(self, *, user_id: UUID, text: str) -> WorkflowResponse | None:
        message = text.strip()
        if not message:
            return WorkflowResponse(message="Please provide a value before continuing.")

        async with self._lock:
            creation = self._creation_workflows.get(user_id)
            if creation is not None:
                return await self._handle_creation_input(
                    user_id=user_id,
                    state=creation,
                    text=message,
                )

            edit = self._edit_workflows.get(user_id)
            if edit is not None:
                return await self._handle_edit_input(user_id=user_id, state=edit, text=message)

        return None

    async def _handle_creation_input(
        self,
        *,
        user_id: UUID,
        state: CreationWorkflowState,
        text: str,
    ) -> WorkflowResponse:
        if state.step == CreationStep.WAITING_FOR_NAME:
            state.name = text
            state.step = CreationStep.WAITING_FOR_DESCRIPTION
            return WorkflowResponse(message="Describe your character.")

        if state.step == CreationStep.WAITING_FOR_DESCRIPTION:
            state.description = text
            state.step = CreationStep.WAITING_FOR_PERSONALITY
            return WorkflowResponse(message="Describe the character's personality.")

        if state.step == CreationStep.WAITING_FOR_PERSONALITY:
            state.personality = text
            state.step = CreationStep.WAITING_FOR_SCENARIO
            return WorkflowResponse(message="Describe the starting scenario.")

        if state.step == CreationStep.WAITING_FOR_SCENARIO:
            state.scenario = text
            state.step = CreationStep.WAITING_FOR_FIRST_MESSAGE
            return WorkflowResponse(message="What is the character's first message?")

        if state.step != CreationStep.WAITING_FOR_FIRST_MESSAGE:
            return WorkflowResponse(message="Workflow state is invalid. Use /cancel and try again.")

        state.first_message = text
        data = CharacterCardData(
            name=state.name,
            description=state.description,
            personality=state.personality,
            scenario=state.scenario,
            first_message=state.first_message,
        )
        errors = self._validate_card_data(data)
        if errors:
            return WorkflowResponse(
                message=(
                    "Validation failed:\n"
                    + "\n".join(f"- {error}" for error in errors)
                    + "\nPlease provide the first message again."
                )
            )

        slug = self._slugify(data.name)
        if not slug:
            return WorkflowResponse(
                message="Character name must contain letters or numbers. Please enter a valid name."
            )

        existing = await self._character_store.get_by_id(slug)
        if existing is not None:
            return WorkflowResponse(
                message=(
                    "A character with this identifier already exists. "
                    "Please enter a different name."
                )
            )

        character = Character(
            id=slug,
            owner_id=user_id,
            visibility=CharacterVisibility.PRIVATE,
            name=data.name,
            description=data.description,
            personality=data.personality,
            greeting=data.first_message,
            metadata={
                "spec": "chara_card_v3",
                "spec_version": "3.0",
                "scenario": data.scenario,
                "first_message": data.first_message,
            },
        )
        await self._character_store.save(character)
        self._creation_workflows.pop(user_id, None)
        return WorkflowResponse(message="Character created successfully.", completed=True)

    async def _handle_edit_input(
        self,
        *,
        user_id: UUID,
        state: EditWorkflowState,
        text: str,
    ) -> WorkflowResponse:
        if state.step == EditStep.WAITING_FOR_FIELD_SELECTION:
            selected = self._parse_edit_field(text)
            if selected is None:
                return WorkflowResponse(
                    message=(
                        "Invalid field selection. Please choose one of: 1, 2, 3, 4, 5 or "
                        "Name, Description, Personality, Scenario, First message."
                    )
                )
            state.selected_field = selected
            state.step = EditStep.WAITING_FOR_FIELD_VALUE
            return WorkflowResponse(message=self._build_edit_value_prompt(selected))

        if state.step != EditStep.WAITING_FOR_FIELD_VALUE or state.selected_field is None:
            return WorkflowResponse(message="Workflow state is invalid. Use /cancel and try again.")

        character = await self._character_store.get_by_id(state.character_id)
        if character is None or character.owner_id != user_id:
            self._edit_workflows.pop(user_id, None)
            return WorkflowResponse(
                message=(
                    "You can only edit characters that you own, and this character "
                    "was not found."
                )
            )

        updated = self._apply_edit(character=character, field=state.selected_field, value=text)
        errors = self._validate_card_data(self._to_card_data(updated))
        if errors:
            return WorkflowResponse(
                message=(
                    "Validation failed:\n"
                    + "\n".join(f"- {error}" for error in errors)
                    + "\nPlease enter a different value."
                )
            )

        await self._character_store.save(updated)
        self._edit_workflows.pop(user_id, None)
        return WorkflowResponse(
            message=f"{self._field_display_name(state.selected_field)} updated successfully.",
            completed=True,
        )

    def _ensure_no_active_workflow(self, *, user_id: UUID) -> str | None:
        if user_id in self._creation_workflows or user_id in self._edit_workflows:
            return "You already have an active operation. Use /cancel before starting a new one."
        return None

    async def _find_owned_character(self, *, user_id: UUID, name_or_id: str) -> Character | None:
        owned_by_name = await self._character_store.find_owned_by_name(
            owner_id=user_id,
            name=name_or_id,
        )
        if owned_by_name is not None:
            return owned_by_name

        candidate_id = self._slugify(name_or_id)
        if not candidate_id:
            return None
        owned_by_id = await self._character_store.get_by_id(candidate_id)
        if owned_by_id is None or owned_by_id.owner_id != user_id:
            return None
        return owned_by_id

    @staticmethod
    def _parse_edit_field(value: str) -> EditableField | None:
        normalized = re.sub(r"\s+", " ", value.strip().lower())
        mapping = {
            "1": EditableField.NAME,
            "name": EditableField.NAME,
            "2": EditableField.DESCRIPTION,
            "description": EditableField.DESCRIPTION,
            "3": EditableField.PERSONALITY,
            "personality": EditableField.PERSONALITY,
            "4": EditableField.SCENARIO,
            "scenario": EditableField.SCENARIO,
            "5": EditableField.FIRST_MESSAGE,
            "first message": EditableField.FIRST_MESSAGE,
            "first_message": EditableField.FIRST_MESSAGE,
            "greeting": EditableField.FIRST_MESSAGE,
        }
        return mapping.get(normalized)

    @staticmethod
    def _build_edit_selection_prompt() -> str:
        return (
            "Choose a field to edit:\n\n"
            "1. Name\n"
            "2. Description\n"
            "3. Personality\n"
            "4. Scenario\n"
            "5. First message"
        )

    @staticmethod
    def _build_edit_value_prompt(field: EditableField) -> str:
        if field == EditableField.DESCRIPTION:
            return (
                "Enter the new description.\n\n"
                "A good description includes:\n"
                "- appearance\n"
                "- role\n"
                "- important traits\n"
                "- background"
            )
        if field == EditableField.NAME:
            return "Enter the new name."
        if field == EditableField.PERSONALITY:
            return "Enter the new personality."
        if field == EditableField.SCENARIO:
            return "Enter the new scenario."
        return "Enter the new first message."

    @staticmethod
    def _field_display_name(field: EditableField) -> str:
        if field == EditableField.FIRST_MESSAGE:
            return "First message"
        return field.value.capitalize()

    @staticmethod
    def _apply_edit(*, character: Character, field: EditableField, value: str) -> Character:
        metadata = dict(character.metadata)
        if field == EditableField.NAME:
            return Character(
                id=character.id,
                owner_id=character.owner_id,
                visibility=character.visibility,
                name=value,
                description=character.description,
                personality=character.personality,
                greeting=character.greeting,
                metadata=metadata,
            )
        if field == EditableField.DESCRIPTION:
            return Character(
                id=character.id,
                owner_id=character.owner_id,
                visibility=character.visibility,
                name=character.name,
                description=value,
                personality=character.personality,
                greeting=character.greeting,
                metadata=metadata,
            )
        if field == EditableField.PERSONALITY:
            return Character(
                id=character.id,
                owner_id=character.owner_id,
                visibility=character.visibility,
                name=character.name,
                description=character.description,
                personality=value,
                greeting=character.greeting,
                metadata=metadata,
            )
        if field == EditableField.SCENARIO:
            metadata["scenario"] = value
            return Character(
                id=character.id,
                owner_id=character.owner_id,
                visibility=character.visibility,
                name=character.name,
                description=character.description,
                personality=character.personality,
                greeting=character.greeting,
                metadata=metadata,
            )

        metadata["first_message"] = value
        return Character(
            id=character.id,
            owner_id=character.owner_id,
            visibility=character.visibility,
            name=character.name,
            description=character.description,
            personality=character.personality,
            greeting=value,
            metadata=metadata,
        )

    @staticmethod
    def _to_card_data(character: Character) -> CharacterCardData:
        return CharacterCardData(
            name=character.name,
            description=character.description,
            personality=character.personality,
            scenario=character.metadata.get("scenario", ""),
            first_message=character.greeting,
        )

    @staticmethod
    def _validate_card_data(data: CharacterCardData) -> list[str]:
        errors: list[str] = []
        if not data.name.strip():
            errors.append("Your character needs a name.")
        if not data.description.strip():
            errors.append("Your character needs a description.")
        if not data.personality.strip():
            errors.append("Your character needs a personality.")
        if not data.scenario.strip():
            errors.append("Your character needs a scenario.")
        if not data.first_message.strip():
            errors.append("Your character needs a first message.")
        return errors

    @staticmethod
    def _slugify(value: str) -> str:
        lowered = value.lower().strip()
        replaced = re.sub(r"[^a-z0-9]+", "-", lowered)
        return replaced.strip("-")
