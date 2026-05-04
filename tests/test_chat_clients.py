import pytest

from backend.app.api_chat_client import OpenAICompatibleChatClient
from backend.app.chat_client_factory import create_chat_client
from backend.app.config import Settings
from backend.app.ollama_client import OllamaClient


def test_chat_factory_defaults_to_ollama(tmp_path):
    settings = Settings(
        docs_dir=tmp_path / "docs",
        indexes_dir=tmp_path / "indexes",
        history_db_path=tmp_path / "history.sqlite3",
        chat_provider="ollama",
    )

    client = create_chat_client(settings)

    assert isinstance(client, OllamaClient)


def test_chat_factory_can_select_api_provider(tmp_path):
    settings = Settings(
        docs_dir=tmp_path / "docs",
        indexes_dir=tmp_path / "indexes",
        history_db_path=tmp_path / "history.sqlite3",
        chat_provider="api",
        api_chat_model="example-model",
    )

    client = create_chat_client(settings)

    assert isinstance(client, OpenAICompatibleChatClient)


def test_chat_factory_can_select_nanogpt_provider(tmp_path):
    settings = Settings(
        docs_dir=tmp_path / "docs",
        indexes_dir=tmp_path / "indexes",
        history_db_path=tmp_path / "history.sqlite3",
        chat_provider="nanogpt",
    )

    client = create_chat_client(settings)

    assert isinstance(client, OpenAICompatibleChatClient)


def test_api_chat_client_sends_openai_compatible_request(tmp_path, monkeypatch):
    settings = Settings(
        docs_dir=tmp_path / "docs",
        indexes_dir=tmp_path / "indexes",
        history_db_path=tmp_path / "history.sqlite3",
        chat_provider="api",
        api_chat_base_url="https://example.test/v1",
        api_chat_model="example-model",
        api_chat_key="",
        api_chat_key_env="DOCASSIST_TEST_API_KEY",
    )
    monkeypatch.setenv("DOCASSIST_TEST_API_KEY", "secret-token")
    captured = {}

    class FakeResponse:
        def raise_for_status(self):
            return None

        def iter_lines(self):
            return iter(
                [
                    b'data: {"choices":[{"delta":{"content":"Remote "}}]}',
                    b'data: {"choices":[{"delta":{"content":"answer"}}]}',
                    b"data: [DONE]",
                ]
            )

    def fake_post(url, headers, json, stream, timeout):
        captured["url"] = url
        captured["headers"] = headers
        captured["json"] = json
        captured["stream"] = stream
        captured["timeout"] = timeout
        return FakeResponse()

    monkeypatch.setattr("backend.app.api_chat_client.requests.post", fake_post)

    answer = OpenAICompatibleChatClient(settings).chat([{"role": "user", "content": "Hi"}])

    assert answer == "Remote answer"
    assert captured["url"] == "https://example.test/v1/chat/completions"
    assert captured["headers"] == {
        "Authorization": "Bearer secret-token",
        "Content-Type": "application/json",
        "Accept": "text/event-stream",
    }
    assert captured["json"]["model"] == "example-model"
    assert captured["json"]["messages"] == [{"role": "user", "content": "Hi"}]
    assert captured["json"]["stream"] is True
    assert captured["stream"] is True


def test_api_chat_client_defaults_to_nanogpt_base_url(tmp_path):
    settings = Settings(
        docs_dir=tmp_path / "docs",
        indexes_dir=tmp_path / "indexes",
        history_db_path=tmp_path / "history.sqlite3",
    )

    client = OpenAICompatibleChatClient(settings)

    assert client.base_url == "https://nano-gpt.com/api/v1"


def test_api_chat_client_requires_api_key(tmp_path, monkeypatch):
    settings = Settings(
        docs_dir=tmp_path / "docs",
        indexes_dir=tmp_path / "indexes",
        history_db_path=tmp_path / "history.sqlite3",
        chat_provider="api",
        api_chat_model="example-model",
        api_chat_key="",
        api_chat_key_env="DOCASSIST_TEST_API_KEY",
    )
    monkeypatch.delenv("DOCASSIST_TEST_API_KEY", raising=False)

    with pytest.raises(RuntimeError, match="Missing API key"):
        OpenAICompatibleChatClient(settings).chat([{"role": "user", "content": "Hi"}])
