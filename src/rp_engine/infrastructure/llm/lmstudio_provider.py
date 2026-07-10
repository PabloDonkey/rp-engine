import asyncio
from urllib.parse import urlparse

import lmstudio as lms

from rp_engine.core.engine.models import PromptPayload
from rp_engine.core.ports import LLMProvider


class LMStudioProvider(LLMProvider):
    def __init__(self, *, model_name: str, api_host: str) -> None:
        self._model_name = model_name
        self._api_host = _normalize_api_host(api_host)

    async def generate_response(self, prompt: PromptPayload) -> str:
        return await asyncio.to_thread(self._generate_sync, prompt)

    def _generate_sync(self, prompt: PromptPayload) -> str:
        lms.configure_default_client(self._api_host)
        model = lms.llm(self._model_name)
        chat = lms.Chat(prompt.system_prompt)
        chat.add_user_message(prompt.user_message)
        result = model.respond(chat)
        return str(result)


def _normalize_api_host(api_host: str) -> str:
    parsed = urlparse(api_host)
    if parsed.scheme and parsed.netloc:
        return parsed.netloc
    return api_host
