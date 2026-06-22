"""LM Studio API client for OpenAI-compatible interface."""

from typing import Optional

import requests
from pydantic import BaseModel, ConfigDict, Field


class ChatMessage(BaseModel):
    """Chat message model."""

    model_config = ConfigDict(frozen=True)

    role: str
    content: str


class ChatCompletionRequest(BaseModel):
    """Chat completion request model."""

    model_config = ConfigDict(frozen=True)

    model: str
    messages: list[ChatMessage]
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    max_tokens: Optional[int] = None
    top_p: float = Field(default=0.9, ge=0.0, le=1.0)


class ChatCompletionChoice(BaseModel):
    """Chat completion choice model."""

    model_config = ConfigDict(frozen=True)

    message: ChatMessage
    finish_reason: str
    index: int


class ChatCompletionResponse(BaseModel):
    """Chat completion response model."""

    model_config = ConfigDict(frozen=True)

    id: str
    object: str
    created: int
    model: str
    choices: list[ChatCompletionChoice]


class LMStudioClient:
    """Client for LM Studio API (OpenAI-compatible)."""

    def __init__(self, api_url: str) -> None:
        """Initialize LM Studio client.

        Args:
            api_url: Base URL for LM Studio API (e.g., http://localhost:1234/v1)
        """
        self.api_url = api_url.rstrip("/")
        self.session = requests.Session()

    def chat_completion(
        self,
        model: str,
        messages: list[ChatMessage],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        top_p: float = 0.9,
    ) -> str:
        """Send a chat completion request to LM Studio.

        Args:
            model: Model name to use
            messages: List of chat messages
            temperature: Sampling temperature (0-2)
            max_tokens: Maximum tokens in response
            top_p: Nucleus sampling parameter

        Returns:
            Response text from the model

        Raises:
            requests.RequestException: If API request fails
            ValueError: If response is malformed
        """
        url = f"{self.api_url}/chat/completions"

        request_data = ChatCompletionRequest(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            top_p=top_p,
        )

        response = self.session.post(
            url, json=request_data.model_dump(exclude_none=True)
        )
        response.raise_for_status()

        data = response.json()
        completion = ChatCompletionResponse.model_validate(data)

        if not completion.choices:
            raise ValueError("No choices in API response")

        return completion.choices[0].message.content

    def close(self) -> None:
        """Close the session."""
        self.session.close()
