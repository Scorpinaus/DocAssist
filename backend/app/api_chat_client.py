import os
import json

import requests

from backend.app.config import Settings


class OpenAICompatibleChatClient:
    """HTTP adapter for NanoGPT/OpenAI-compatible streaming chat APIs."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.base_url = _configured_base_url(settings).rstrip("/")

    def chat(self, messages: list[dict[str, str]]) -> str:
        """Stream chat messages from a remote API and return the full assistant content."""
        api_key = self.settings.api_chat_key or os.getenv(self.settings.api_chat_key_env)
        if not api_key:
            raise RuntimeError(
                "Missing API key. Add llm_api_key to data/local_settings.json "
                f"or set {self.settings.api_chat_key_env}."
            )
        if not self.settings.api_chat_model:
            raise RuntimeError("Missing API chat model. Set DOCASSIST_API_CHAT_MODEL.")

        response = requests.post(
            f"{self.base_url}/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "Accept": "text/event-stream",
            },
            json={
                "model": self.settings.api_chat_model,
                "messages": messages,
                "stream": True,
            },
            stream=True,
            timeout=180,
        )
        response.raise_for_status()
        return "".join(_iter_stream_content(response)).strip()


def _iter_stream_content(response):
    for line in response.iter_lines():
        if not line:
            continue
        decoded = line.decode("utf-8")
        if decoded.startswith("data: "):
            decoded = decoded[6:]
        if decoded == "[DONE]":
            break
        try:
            chunk = json.loads(decoded)
        except json.JSONDecodeError:
            continue
        choices = chunk.get("choices") or []
        if choices:
            content = choices[0].get("delta", {}).get("content")
            if content:
                yield content


def _configured_base_url(settings: Settings) -> str:
    if settings.api_chat_base_url:
        return settings.api_chat_base_url
    return "https://nano-gpt.com/api/v1"
