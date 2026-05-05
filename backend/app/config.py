import json
import os
from dataclasses import dataclass, field
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
LOCAL_SETTINGS_PATH = PROJECT_ROOT / "data" / "local_settings.json"
LOCAL_SETTINGS = {}

if LOCAL_SETTINGS_PATH.exists():
    LOCAL_SETTINGS = json.loads(LOCAL_SETTINGS_PATH.read_text(encoding="utf-8"))


def _setting(name: str, default: str = "") -> str:
    """Read a setting from local JSON first, then environment variables."""
    value = LOCAL_SETTINGS.get(name)
    if value is not None:
        return str(value)
    return os.getenv(f"DOCASSIST_{name.upper()}", default)


def _optional_float_setting(name: str) -> float | None:
    value = _setting(name, "")
    return float(value) if value != "" else None


def _optional_int_setting(name: str) -> int | None:
    value = _setting(name, "")
    return int(value) if value != "" else None


def _int_setting(name: str, default: int) -> int:
    return int(_setting(name, str(default)))


@dataclass(frozen=True)
class Settings:
    """Runtime configuration for local documents, indexes, and model providers."""

    docs_dir: Path = PROJECT_ROOT / "docs"
    indexes_dir: Path = PROJECT_ROOT / "indexes"
    history_db_path: Path = PROJECT_ROOT / "data" / "docassist.sqlite3"
    frontend_dir: Path = PROJECT_ROOT / "frontend"
    default_version: str = "jdk8"
    ollama_base_url: str = "http://localhost:11434"
    ollama_chat_model: str = "qwen3.5:9b"
    ollama_embed_model: str = "embeddinggemma"
    chat_provider: str = field(default_factory=lambda: _setting("chat_provider", "ollama"))
    query_planner: str = field(default_factory=lambda: _setting("query_planner", "deterministic"))
    api_chat_base_url: str = field(default_factory=lambda: _setting("api_chat_base_url", ""))
    api_chat_model: str = field(default_factory=lambda: _setting("api_chat_model", "deepseek/deepseek-v4-flash"))
    api_chat_key: str = field(default_factory=lambda: _setting("llm_api_key", ""), repr=False)
    api_chat_key_env: str = field(default_factory=lambda: _setting("api_chat_key_env", "DOCASSIST_LLM_API_KEY"))
    top_k_results: int = field(default_factory=lambda: _int_setting("top_k_results", 6))
    chunk_size: int = 1200
    chunk_overlap: int = 200
    batch_size: int = 32
    history_limit: int = 100
    generation_temperature: float | None = field(default_factory=lambda: _optional_float_setting("generation_temperature"))
    generation_top_p: float | None = field(default_factory=lambda: _optional_float_setting("generation_top_p"))
    generation_max_tokens: int | None = field(default_factory=lambda: _optional_int_setting("generation_max_tokens"))
    generation_frequency_penalty: float | None = field(default_factory=lambda: _optional_float_setting("generation_frequency_penalty"))
    generation_presence_penalty: float | None = field(default_factory=lambda: _optional_float_setting("generation_presence_penalty"))
    generation_reasoning_effort: str = field(default_factory=lambda: _setting("generation_reasoning_effort", ""))
    generation_context_window: int | None = field(default_factory=lambda: _optional_int_setting("generation_context_window"))


settings = Settings()
