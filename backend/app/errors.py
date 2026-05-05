import requests

from backend.app.config import Settings


def friendly_runtime_error(error: Exception, settings: Settings) -> str:
    """Return a user-facing message for known runtime dependency failures."""
    if is_embedding_connection_error(error):
        return embedding_unavailable_message(settings)
    return str(error)


def is_embedding_connection_error(error: Exception) -> bool:
    """Return whether an exception came from the local embedding HTTP service."""
    return isinstance(error, requests.RequestException)


def embedding_unavailable_message(settings: Settings) -> str:
    """Explain that local embeddings require Ollama, even for remote answer models."""
    return (
        f"Ollama embeddings are unavailable at {settings.ollama_base_url}. "
        f"Start Ollama, make sure the embedding model '{settings.ollama_embed_model}' is installed, then retry."
    )
