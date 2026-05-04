from backend.app.config import Settings
from backend.app.ollama_client import OllamaClient
from backend.app.vector_store import VectorStore


class Retriever:
    """Coordinates query embedding and vector search for a documentation version."""

    def __init__(self, settings: Settings, ollama_client: OllamaClient | None = None):
        """Create a retriever with injectable dependencies for tests."""
        self.settings = settings
        self.ollama_client = ollama_client or OllamaClient(settings)
        self.vector_store = VectorStore(settings.indexes_dir)

    def retrieve(self, version: str, query: str, top_k: int):
        """Return the most relevant chunks for a user query."""
        embeddings = self.ollama_client.embed(query)
        if not embeddings:
            return []
        return self.vector_store.query(version, embeddings[0], top_k)
