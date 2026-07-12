from collections.abc import Callable
from typing import Any

import pytest

from rp_engine.core.conversation.conversation import Conversation
from rp_engine.core.conversation.message import ConversationMessage
from rp_engine.core.conversation.role import ConversationRole
from rp_engine.infrastructure.llm.lmstudio_provider import LMStudioProvider


class FakeChat:
    def __init__(self, system_prompt: str) -> None:
        self.system_prompt = system_prompt
        self.user_messages: list[str] = []
        self.assistant_messages: list[str] = []

    def add_user_message(self, message: str) -> None:
        self.user_messages.append(message)

    def add_assistant_message(self, message: str) -> None:
        self.assistant_messages.append(message)


class FakeModel:
    def __init__(self, responder: Callable[[FakeChat], str]) -> None:
        self._responder = responder
        self.last_config: Any = None

    def respond(self, chat: FakeChat, *, config: Any = None) -> str:
        self.last_config = config
        return self._responder(chat)


def _conversation() -> Conversation:
    return Conversation(
        messages=[
            ConversationMessage(role=ConversationRole.SYSTEM, content="sys-a"),
            ConversationMessage(role=ConversationRole.SYSTEM, content="sys-b"),
            ConversationMessage(role=ConversationRole.CHARACTER, content="prior response"),
            ConversationMessage(role=ConversationRole.USER, content="hello"),
        ]
    )


@pytest.mark.asyncio
async def test_lmstudio_provider_uses_sdk_calls(monkeypatch: pytest.MonkeyPatch) -> None:
    configured_hosts: list[str] = []
    model_names: list[str] = []

    def fake_configure_default_client(host: str) -> None:
        configured_hosts.append(host)

    def fake_llm(name: str) -> FakeModel:
        model_names.append(name)

        def respond(chat: FakeChat) -> str:
            return f"{chat.system_prompt}|{chat.user_messages[0]}|{chat.assistant_messages[0]}"

        return FakeModel(respond)

    monkeypatch.setattr(
        "rp_engine.infrastructure.llm.lmstudio_provider.lms.configure_default_client",
        fake_configure_default_client,
    )
    monkeypatch.setattr("rp_engine.infrastructure.llm.lmstudio_provider.lms.llm", fake_llm)
    monkeypatch.setattr("rp_engine.infrastructure.llm.lmstudio_provider.lms.Chat", FakeChat)
    monkeypatch.setattr(LMStudioProvider, "_configured_api_host", None)

    provider = LMStudioProvider(
        model_name="model-a",
        api_host="http://127.0.0.1:1234",
        max_tokens=600,
        temperature=0.8,
    )
    result = await provider.generate_response(_conversation())

    assert configured_hosts == ["127.0.0.1:1234"]
    assert model_names == ["model-a"]
    assert result == "sys-a\n\nsys-b|hello|prior response"


@pytest.mark.asyncio
async def test_lmstudio_provider_configures_client_only_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    configured_hosts: list[str] = []

    def fake_configure_default_client(host: str) -> None:
        configured_hosts.append(host)

    def fake_llm(_: str) -> FakeModel:
        return FakeModel(lambda chat: chat.user_messages[0])

    monkeypatch.setattr(
        "rp_engine.infrastructure.llm.lmstudio_provider.lms.configure_default_client",
        fake_configure_default_client,
    )
    monkeypatch.setattr("rp_engine.infrastructure.llm.lmstudio_provider.lms.llm", fake_llm)
    monkeypatch.setattr("rp_engine.infrastructure.llm.lmstudio_provider.lms.Chat", FakeChat)
    monkeypatch.setattr(LMStudioProvider, "_configured_api_host", None)

    provider = LMStudioProvider(
        model_name="model-a",
        api_host="127.0.0.1:1234",
        max_tokens=600,
        temperature=0.8,
    )
    first = await provider.generate_response(
        Conversation(messages=[ConversationMessage(role=ConversationRole.USER, content="one")])
    )
    second = await provider.generate_response(
        Conversation(messages=[ConversationMessage(role=ConversationRole.USER, content="two")])
    )

    assert configured_hosts == ["127.0.0.1:1234"]
    assert first == "one"
    assert second == "two"


@pytest.mark.asyncio
async def test_lmstudio_provider_passes_prediction_config(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    model_instances: list[FakeModel] = []

    def fake_configure_default_client(_: str) -> None:
        return None

    def fake_llm(_: str) -> FakeModel:
        model = FakeModel(lambda _chat: "ok")
        model_instances.append(model)
        return model

    monkeypatch.setattr(
        "rp_engine.infrastructure.llm.lmstudio_provider.lms.configure_default_client",
        fake_configure_default_client,
    )
    monkeypatch.setattr("rp_engine.infrastructure.llm.lmstudio_provider.lms.llm", fake_llm)
    monkeypatch.setattr("rp_engine.infrastructure.llm.lmstudio_provider.lms.Chat", FakeChat)
    monkeypatch.setattr(LMStudioProvider, "_configured_api_host", None)

    provider = LMStudioProvider(
        model_name="model-a",
        api_host="127.0.0.1:1234",
        max_tokens=600,
        temperature=0.7,
    )

    result = await provider.generate_response(
        Conversation(messages=[ConversationMessage(role=ConversationRole.USER, content="hi")])
    )

    assert result == "ok"
    last_config = model_instances[0].last_config
    assert last_config is not None
    assert last_config.max_tokens == 600
    assert last_config.temperature == 0.7
