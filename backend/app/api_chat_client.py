import os
import json

import requests

from backend.app.config import Settings


class OpenAICompatibleChatClient:
    """HTTP adapter for NanoGPT/OpenAI-compatible streaming chat APIs."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.base_url = _configured_base_url(settings).rstrip("/")

    def chat(self, messages: list[dict[str, str]], options=None) -> str:
        """Stream chat messages from a remote API and return the full assistant content."""
        api_key = self.settings.api_chat_key or os.getenv(self.settings.api_chat_key_env)
        if not api_key:
            raise RuntimeError(
                "Missing API key. Add llm_api_key to data/local_settings.json "
                f"or set {self.settings.api_chat_key_env}."
            )
        if not self.settings.api_chat_model:
            raise RuntimeError("Missing API chat model. Set DOCASSIST_API_CHAT_MODEL.")

        request_payload = {
            "model": self.settings.api_chat_model,
            "messages": messages,
            "stream": True,
            **_openai_generation_options(options),
        }
        response = requests.post(
            f"{self.base_url}/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "Accept": "text/event-stream",
            },
            json=request_payload,
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


def _openai_generation_options(options) -> dict:
    payload = {}
    temperature = _option_value(options, "temperature")
    top_p = _option_value(options, "top_p", "topP")
    max_tokens = _option_value(options, "max_tokens", "maxTokens")
    frequency_penalty = _option_value(options, "frequency_penalty", "frequencyPenalty")
    presence_penalty = _option_value(options, "presence_penalty", "presencePenalty")
    reasoning_effort = _option_value(options, "reasoning_effort", "reasoningEffort")
    if temperature is not None:
        payload["temperature"] = temperature
    if top_p is not None:
        payload["top_p"] = top_p
    if max_tokens is not None:
        payload["max_tokens"] = max_tokens
    if frequency_penalty is not None:
        payload["frequency_penalty"] = frequency_penalty
    if presence_penalty is not None:
        payload["presence_penalty"] = presence_penalty
    if reasoning_effort is not None:
        payload["reasoning_effort"] = reasoning_effort
    return payload


def _option_value(options, *names):
    if options is None:
        return None
    for name in names:
        if isinstance(options, dict):
            if name in options:
                return options[name]
        elif hasattr(options, name):
            return getattr(options, name)
    return None
