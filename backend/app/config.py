from dataclasses import dataclass
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class Settings:
    """Runtime configuration for local documents, indexes, and Ollama models."""

    docs_dir: Path = PROJECT_ROOT / "docs"
    indexes_dir: Path = PROJECT_ROOT / "indexes"
    history_db_path: Path = PROJECT_ROOT / "data" / "docassist.sqlite3"
    frontend_dir: Path = PROJECT_ROOT / "frontend"
    default_version: str = "jdk8"
    ollama_base_url: str = "http://localhost:11434"
    ollama_chat_model: str = "qwen3.5:9b"
    ollama_embed_model: str = "embeddinggemma"
    top_k_results: int = 6
    chunk_size: int = 1200
    chunk_overlap: int = 200
    batch_size: int = 32
    history_limit: int = 100


settings = Settings()
