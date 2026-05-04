from backend.app.api_chat_client import OpenAICompatibleChatClient
from backend.app.config import Settings
from backend.app.ollama_client import OllamaClient


def create_chat_client(settings: Settings):
    """Create the configured answer-generation client."""
    provider = settings.chat_provider.strip().lower()
    if provider == "ollama":
        return OllamaClient(settings)
    if provider in {"nanogpt", "nano-gpt", "openai", "openai-compatible", "api"}:
        return OpenAICompatibleChatClient(settings)
    raise ValueError(f"Unsupported chat provider: {settings.chat_provider}")
