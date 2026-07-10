import asyncio
import logging
from threading import Lock
from typing import ClassVar
from urllib.parse import urlparse

import lmstudio as lms

from rp_engine.core.engine.models import PromptPayload
from rp_engine.core.ports import LLMProvider

logger = logging.getLogger(__name__)


class LMStudioProvider(LLMProvider):
    _client_lock: ClassVar[Lock] = Lock()
    _configured_api_host: ClassVar[str | None] = None

    def __init__(self, *, model_name: str, api_host: str) -> None:
        self._model_name = model_name
        self._api_host = _normalize_api_host(api_host)
        self._ensure_default_client_configured(self._api_host)

    async def generate_response(self, prompt: PromptPayload) -> str:
        logger.info("LLM request sent", extra={"model_name": self._model_name})
        try:
            return await asyncio.to_thread(self._generate_sync, prompt)
        except Exception:
            logger.exception("LLM unavailable", extra={"model_name": self._model_name})
            raise

    def _generate_sync(self, prompt: PromptPayload) -> str:
        model = lms.llm(self._model_name)
        chat = lms.Chat(prompt.system_prompt)
        chat.add_user_message(prompt.user_message)
        result = model.respond(chat)
        return str(result)

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
