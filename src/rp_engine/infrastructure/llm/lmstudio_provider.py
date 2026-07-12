import asyncio
import logging
from threading import Lock
from typing import ClassVar
from urllib.parse import urlparse

import lmstudio as lms

from rp_engine.core.conversation.conversation import Conversation
from rp_engine.core.conversation.message import ConversationMessage
from rp_engine.core.conversation.role import ConversationRole
from rp_engine.core.ports import LLMProvider

logger = logging.getLogger(__name__)


class LMStudioProvider(LLMProvider):
    _client_lock: ClassVar[Lock] = Lock()
    _configured_api_host: ClassVar[str | None] = None

    def __init__(
        self,
        *,
        model_name: str,
        api_host: str,
        max_tokens: int,
        temperature: float,
        top_k_sampling: int = 40,
        repeat_penalty: float = 1.1,
        top_p_sampling: float = 0.95,
        min_p_sampling: float = 0.05,
    ) -> None:
        self._model_name = model_name
        self._api_host = _normalize_api_host(api_host)
        self._max_tokens = max_tokens
        self._temperature = temperature
        self._top_k_sampling = top_k_sampling
        self._repeat_penalty = repeat_penalty
        self._top_p_sampling = top_p_sampling
        self._min_p_sampling = min_p_sampling
        self._ensure_default_client_configured(self._api_host)

    async def generate_response(self, conversation: Conversation) -> str:
        logger.info("LLM request sent", extra={"model_name": self._model_name})
        try:
            return await asyncio.to_thread(self._generate_sync, conversation)
        except Exception:
            logger.exception("LLM unavailable", extra={"model_name": self._model_name})
            raise

    def _generate_sync(self, conversation: Conversation) -> str:
        model = lms.llm(self._model_name)
        system_prompt = self._build_system_prompt(conversation.messages)
        chat = lms.Chat(system_prompt)
        for message in conversation.messages:
            if message.role == ConversationRole.SYSTEM:
                continue
            if message.role == ConversationRole.USER:
                chat.add_user_message(message.content)
                continue
            self._add_character_message(chat=chat, content=message.content)

        config = self._get_config()
        logger.info(
            "LmStudio.generate_response",
            extra={"config": str(config)},
        )
        result = model.respond(
            chat,
            config=config,
        )
        stats = getattr(result, "stats", None)
        if stats is not None:
            logger.info("Response statistics", extra={"stats": str(stats)})
        return str(result)

    @staticmethod
    def _build_system_prompt(messages: list[ConversationMessage]) -> str:
        system_parts = [
            message.content.strip()
            for message in messages
            if message.role == ConversationRole.SYSTEM and message.content.strip()
        ]
        if not system_parts:
            return "You are a roleplay character."
        return "\n\n".join(system_parts)

    @staticmethod
    def _add_character_message(*, chat: object, content: str) -> None:
        add_assistant = getattr(chat, "add_assistant_message", None)
        if callable(add_assistant):
            add_assistant(content)
            return

        add_user = getattr(chat, "add_user_message", None)
        if callable(add_user):
            add_user(f"Character: {content}")
            return

        raise TypeError("LM Studio chat object does not support adding messages.")

    def _get_config(self) -> lms.LlmPredictionConfig:
        return lms.LlmPredictionConfig(   
            max_tokens=self._max_tokens,
            temperature=self._temperature,
            top_k_sampling=self._top_k_sampling,
            repeat_penalty=self._repeat_penalty,
            top_p_sampling=self._top_p_sampling,
            min_p_sampling=self._min_p_sampling,
        )

    @classmethod
    def _ensure_default_client_configured(cls, api_host: str) -> None:
        with cls._client_lock:
            configured_host = cls._configured_api_host
            if configured_host is None:
                lms.configure_default_client(api_host)
                cls._configured_api_host = api_host
                return

            if configured_host != api_host:
                msg = (
                    "LM Studio client is already configured for "
                    f"{configured_host} and cannot be reconfigured to {api_host}."
                )
                raise ValueError(msg)


def _normalize_api_host(api_host: str) -> str:
    parsed = urlparse(api_host)
    if parsed.scheme and parsed.netloc:
        return parsed.netloc
    return api_host
