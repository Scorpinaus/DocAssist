from backend.app.api_chat_client import OpenAICompatibleChatClient
from backend.app.config import Settings
from backend.app.ollama_client import OllamaClient


def normalize_chat_provider(provider: str) -> str:
    """Normalize chat provider aliases used by config, API, and UI."""
    normalized = provider.strip().lower()
    if normalized in {"nano-gpt", "openai", "openai-compatible", "api"}:
        return "nanogpt"
    return normalized


def create_chat_client(settings: Settings, provider: str | None = None):
    """Create the configured answer-generation client."""
    normalized = normalize_chat_provider(provider or settings.chat_provider)
    if normalized == "ollama":
        return OllamaClient(settings)
    if normalized == "nanogpt":
        return OpenAICompatibleChatClient(settings)
    raise ValueError(f"Unsupported chat provider: {provider or settings.chat_provider}")
