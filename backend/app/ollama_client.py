import requests

from backend.app.config import Settings


class OllamaClient:
    """Small HTTP adapter for Ollama chat and embedding endpoints."""

    def __init__(self, settings: Settings):
        """Store model settings and normalize the Ollama base URL."""
        self.settings = settings
        self.base_url = settings.ollama_base_url.rstrip("/")

    def embed(self, inputs: str | list[str]) -> list[list[float]]:
        """Request embeddings for one string or a batch of strings."""
        response = requests.post(
            f"{self.base_url}/api/embed",
            json={"model": self.settings.ollama_embed_model, "input": inputs},
            timeout=120,
        )
        response.raise_for_status()
        payload = response.json()
        embeddings = payload.get("embeddings")
        if embeddings is None:
            raise RuntimeError("Ollama embed response did not contain embeddings")
        return embeddings

    def chat(self, messages: list[dict[str, str]], options=None) -> str:
        """Send chat messages to Ollama and return the assistant content."""
        payload = {
            "model": self.settings.ollama_chat_model,
            "messages": messages,
            "stream": False,
        }
        generation_options = _ollama_generation_options(options)
        if generation_options:
            payload["options"] = generation_options
        response = requests.post(
            f"{self.base_url}/api/chat",
            json=payload,
            timeout=180,
        )
        response.raise_for_status()
        payload = response.json()
        return payload.get("message", {}).get("content", "").strip()


def _ollama_generation_options(options) -> dict:
    payload = {}
    temperature = _option_value(options, "temperature")
    top_p = _option_value(options, "top_p", "topP")
    max_tokens = _option_value(options, "max_tokens", "maxTokens")
    context_window = _option_value(options, "context_window", "contextWindow")
    if temperature is not None:
        payload["temperature"] = temperature
    if top_p is not None:
        payload["top_p"] = top_p
    if max_tokens is not None:
        payload["num_predict"] = max_tokens
    if context_window is not None:
        payload["num_ctx"] = context_window
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
