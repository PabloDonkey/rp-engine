from collections.abc import Callable

import pytest

from rp_engine.core.engine.models import PromptPayload
from rp_engine.infrastructure.llm.lmstudio_provider import LMStudioProvider


class FakeChat:
    def __init__(self, system_prompt: str) -> None:
        self.system_prompt = system_prompt
        self.user_messages: list[str] = []

    def add_user_message(self, message: str) -> None:
        self.user_messages.append(message)


class FakeModel:
    def __init__(self, responder: Callable[[FakeChat], str]) -> None:
        self._responder = responder

    def respond(self, chat: FakeChat) -> str:
        return self._responder(chat)


@pytest.mark.asyncio
async def test_lmstudio_provider_uses_sdk_calls(monkeypatch: pytest.MonkeyPatch) -> None:
    configured_hosts: list[str] = []
    model_names: list[str] = []

    def fake_configure_default_client(host: str) -> None:
        configured_hosts.append(host)

    def fake_llm(name: str) -> FakeModel:
        model_names.append(name)

        def respond(chat: FakeChat) -> str:
            return f"{chat.system_prompt}|{chat.user_messages[0]}"

        return FakeModel(respond)

    monkeypatch.setattr(
        "rp_engine.infrastructure.llm.lmstudio_provider.lms.configure_default_client",
        fake_configure_default_client,
    )
    monkeypatch.setattr("rp_engine.infrastructure.llm.lmstudio_provider.lms.llm", fake_llm)
    monkeypatch.setattr("rp_engine.infrastructure.llm.lmstudio_provider.lms.Chat", FakeChat)
    monkeypatch.setattr(LMStudioProvider, "_configured_api_host", None)

    provider = LMStudioProvider(model_name="model-a", api_host="http://127.0.0.1:1234")
    result = await provider.generate_response(
        PromptPayload(system_prompt="sys", user_message="hello")
    )

    assert configured_hosts == ["127.0.0.1:1234"]
    assert model_names == ["model-a"]
    assert result == "sys|hello"


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

    provider = LMStudioProvider(model_name="model-a", api_host="127.0.0.1:1234")
    first = await provider.generate_response(PromptPayload(system_prompt="sys", user_message="one"))
    second = await provider.generate_response(
        PromptPayload(system_prompt="sys", user_message="two")
    )

    assert configured_hosts == ["127.0.0.1:1234"]
    assert first == "one"
    assert second == "two"
