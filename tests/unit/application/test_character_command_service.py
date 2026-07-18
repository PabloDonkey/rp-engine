from __future__ import annotations

from uuid import UUID

import pytest

from rp_engine.application.services.character_command_service import CharacterCommandService
from rp_engine.core.character.character import Character
from rp_engine.core.character.visibility import CharacterVisibility

OWNER_ID = UUID("00000000-0000-0000-0000-000000000042")
OTHER_OWNER_ID = UUID("00000000-0000-0000-0000-000000000777")


class InMemoryCharacterStore:
    def __init__(self) -> None:
        self._items: dict[str, Character] = {}

    async def get_by_id(self, character_id: str) -> Character | None:
        return self._items.get(character_id)

    async def find_by_name(self, name: str) -> Character | None:
        target = name.strip().lower()
        for value in self._items.values():
            if value.name.strip().lower() == target:
                return value
        return None

    async def find_owned_by_name(self, *, owner_id: UUID, name: str) -> Character | None:
        target = name.strip().lower()
        for value in self._items.values():
            if value.owner_id == owner_id and value.name.strip().lower() == target:
                return value
        return None

    async def create_minimal(
        self,
        *,
        character_id: str,
        owner_id: UUID,
        name: str,
        visibility: CharacterVisibility = CharacterVisibility.PRIVATE,
    ) -> Character:
        existing = self._items.get(character_id)
        if existing is not None:
            return existing
        created = Character(
            id=character_id,
            owner_id=owner_id,
            visibility=visibility,
            name=name,
            description=f"Character profile for {name}.",
            personality="Open-ended roleplay persona.",
            greeting="",
            metadata={},
        )
        self._items[character_id] = created
        return created

    async def save(self, character: Character) -> Character:
        self._items[character.id] = character
        return character


@pytest.mark.asyncio
async def test_creation_flow_completes_five_steps_and_persists_all_fields() -> None:
    store = InMemoryCharacterStore()
    service = CharacterCommandService(character_store=store)

    start = await service.start_creation(user_id=OWNER_ID)
    assert start.message == "What is the character name?"

    response = await service.handle_user_input(user_id=OWNER_ID, text="Belzebuth")
    assert response is not None
    assert response.message == "Describe your character."

    response = await service.handle_user_input(user_id=OWNER_ID, text="Ancient dragon mage")
    assert response is not None
    assert response.message == "Describe the character's personality."

    response = await service.handle_user_input(user_id=OWNER_ID, text="Wise and ruthless")
    assert response is not None
    assert response.message == "Describe the starting scenario."

    response = await service.handle_user_input(user_id=OWNER_ID, text="Ruined temple")
    assert response is not None
    assert response.message == "What is the character's first message?"

    response = await service.handle_user_input(user_id=OWNER_ID, text="Who dares wake me?")
    assert response is not None
    assert response.message == "Character created successfully."
    assert response.completed is True

    created = await store.get_by_id("belzebuth")
    assert created is not None
    assert created.owner_id == OWNER_ID
    assert created.visibility == CharacterVisibility.PRIVATE
    assert created.name == "Belzebuth"
    assert created.description == "Ancient dragon mage"
    assert created.personality == "Wise and ruthless"
    assert created.greeting == "Who dares wake me?"
    assert created.metadata["scenario"] == "Ruined temple"
    assert created.metadata["spec"] == "chara_card_v3"


@pytest.mark.asyncio
async def test_creation_validation_failure_requests_correction() -> None:
    store = InMemoryCharacterStore()
    service = CharacterCommandService(character_store=store)

    await service.start_creation(user_id=OWNER_ID)
    await service.handle_user_input(user_id=OWNER_ID, text="Belzebuth")
    await service.handle_user_input(user_id=OWNER_ID, text="Ancient dragon mage")
    await service.handle_user_input(user_id=OWNER_ID, text="Wise and ruthless")
    await service.handle_user_input(user_id=OWNER_ID, text="Ruined temple")

    response = await service.handle_user_input(user_id=OWNER_ID, text="   ")
    assert response is not None
    assert "Please provide a value before continuing." in response.message

    corrected = await service.handle_user_input(user_id=OWNER_ID, text="Who dares wake me?")
    assert corrected is not None
    assert corrected.message == "Character created successfully."


@pytest.mark.asyncio
async def test_cancel_behavior_for_active_and_missing_workflow() -> None:
    store = InMemoryCharacterStore()
    service = CharacterCommandService(character_store=store)

    await service.start_creation(user_id=OWNER_ID)
    cancelled = await service.cancel(user_id=OWNER_ID)
    assert cancelled.message == "Current operation cancelled."

    empty_cancel = await service.cancel(user_id=OWNER_ID)
    assert empty_cancel.message == "No active operation to cancel."


@pytest.mark.asyncio
async def test_edit_flow_field_selection_by_number_updates_character() -> None:
    store = InMemoryCharacterStore()
    service = CharacterCommandService(character_store=store)
    original = Character(
        id="belzebuth",
        owner_id=OWNER_ID,
        visibility=CharacterVisibility.PRIVATE,
        name="Belzebuth",
        description="Old description",
        personality="Old personality",
        greeting="Old hello",
        metadata={"scenario": "Old scenario", "spec": "chara_card_v3", "spec_version": "3.0"},
    )
    await store.save(original)

    started = await service.start_edit(user_id=OWNER_ID, character_name="Belzebuth")
    assert "Choose a field to edit" in started.message

    field_selected = await service.handle_user_input(user_id=OWNER_ID, text="2")
    assert field_selected is not None
    assert "Enter the new description." in field_selected.message

    updated = await service.handle_user_input(user_id=OWNER_ID, text="Ancient dragon mage")
    assert updated is not None
    assert updated.message == "Description updated successfully."

    loaded = await store.get_by_id("belzebuth")
    assert loaded is not None
    assert loaded.description == "Ancient dragon mage"
    assert loaded.personality == "Old personality"


@pytest.mark.asyncio
async def test_edit_flow_field_selection_by_text_updates_character() -> None:
    store = InMemoryCharacterStore()
    service = CharacterCommandService(character_store=store)
    original = Character(
        id="belzebuth",
        owner_id=OWNER_ID,
        visibility=CharacterVisibility.PRIVATE,
        name="Belzebuth",
        description="Old description",
        personality="Old personality",
        greeting="Old hello",
        metadata={"scenario": "Old scenario", "spec": "chara_card_v3", "spec_version": "3.0"},
    )
    await store.save(original)

    await service.start_edit(user_id=OWNER_ID, character_name="Belzebuth")
    selected = await service.handle_user_input(user_id=OWNER_ID, text="scenario")
    assert selected is not None
    assert selected.message == "Enter the new scenario."

    updated = await service.handle_user_input(user_id=OWNER_ID, text="Ruined temple")
    assert updated is not None
    assert updated.message == "Scenario updated successfully."

    loaded = await store.get_by_id("belzebuth")
    assert loaded is not None
    assert loaded.metadata["scenario"] == "Ruined temple"


@pytest.mark.asyncio
async def test_edit_rejects_non_owner() -> None:
    store = InMemoryCharacterStore()
    service = CharacterCommandService(character_store=store)
    original = Character(
        id="belzebuth",
        owner_id=OTHER_OWNER_ID,
        visibility=CharacterVisibility.PRIVATE,
        name="Belzebuth",
        description="Old description",
        personality="Old personality",
        greeting="Old hello",
        metadata={"scenario": "Old scenario", "spec": "chara_card_v3", "spec_version": "3.0"},
    )
    await store.save(original)

    started = await service.start_edit(user_id=OWNER_ID, character_name="Belzebuth")
    assert "only edit characters that you own" in started.message


@pytest.mark.asyncio
async def test_edit_validation_failure_keeps_old_value() -> None:
    store = InMemoryCharacterStore()
    service = CharacterCommandService(character_store=store)
    original = Character(
        id="belzebuth",
        owner_id=OWNER_ID,
        visibility=CharacterVisibility.PRIVATE,
        name="Belzebuth",
        description="Old description",
        personality="Old personality",
        greeting="Old hello",
        metadata={"scenario": "Old scenario", "spec": "chara_card_v3", "spec_version": "3.0"},
    )
    await store.save(original)

    await service.start_edit(user_id=OWNER_ID, character_name="Belzebuth")
    await service.handle_user_input(user_id=OWNER_ID, text="personality")
    failed = await service.handle_user_input(user_id=OWNER_ID, text="   ")
    assert failed is not None
    assert "Please provide a value before continuing." in failed.message

    loaded = await store.get_by_id("belzebuth")
    assert loaded is not None
    assert loaded == original

    corrected = await service.handle_user_input(user_id=OWNER_ID, text="Disciplined and calm")
    assert corrected is not None
    assert corrected.message == "Personality updated successfully."

    updated = await store.get_by_id("belzebuth")
    assert updated is not None
    assert updated.personality == "Disciplined and calm"
