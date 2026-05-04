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

    def chat(self, messages: list[dict[str, str]]) -> str:
        """Send chat messages to Ollama and return the assistant content."""
        response = requests.post(
            f"{self.base_url}/api/chat",
            json={
                "model": self.settings.ollama_chat_model,
                "messages": messages,
                "stream": False,
            },
            timeout=180,
        )
        response.raise_for_status()
        payload = response.json()
        return payload.get("message", {}).get("content", "").strip()
