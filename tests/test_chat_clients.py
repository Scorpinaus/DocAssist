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


def test_api_chat_client_sends_supported_generation_options(tmp_path, monkeypatch):
    settings = Settings(
        docs_dir=tmp_path / "docs",
        indexes_dir=tmp_path / "indexes",
        history_db_path=tmp_path / "history.sqlite3",
        chat_provider="api",
        api_chat_base_url="https://example.test/v1",
        api_chat_model="example-model",
        api_chat_key="test-token",
    )
    captured = {}

    class FakeResponse:
        def raise_for_status(self):
            return None

        def iter_lines(self):
            return iter([b'data: {"choices":[{"delta":{"content":"Done"}}]}', b"data: [DONE]"])

    def fake_post(url, headers, json, stream, timeout):
        captured["json"] = json
        return FakeResponse()

    monkeypatch.setattr("backend.app.api_chat_client.requests.post", fake_post)

    OpenAICompatibleChatClient(settings).chat(
        [{"role": "user", "content": "Hi"}],
        options={
            "temperature": 0.4,
            "topP": 0.85,
            "maxTokens": 500,
            "frequencyPenalty": 0.1,
            "presencePenalty": 0.2,
            "reasoningEffort": "high",
            "contextWindow": 4096,
            "topKResults": 3,
        },
    )

    assert captured["json"]["temperature"] == 0.4
    assert captured["json"]["top_p"] == 0.85
    assert captured["json"]["max_tokens"] == 500
    assert captured["json"]["frequency_penalty"] == 0.1
    assert captured["json"]["presence_penalty"] == 0.2
    assert captured["json"]["reasoning_effort"] == "high"
    assert "contextWindow" not in captured["json"]
    assert "topKResults" not in captured["json"]


def test_ollama_chat_client_sends_supported_generation_options(tmp_path, monkeypatch):
    settings = Settings(
        docs_dir=tmp_path / "docs",
        indexes_dir=tmp_path / "indexes",
        history_db_path=tmp_path / "history.sqlite3",
        ollama_chat_model="example-model",
    )
    captured = {}

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"message": {"content": "Local answer"}}

    def fake_post(url, json, timeout):
        captured["url"] = url
        captured["json"] = json
        return FakeResponse()

    monkeypatch.setattr("backend.app.ollama_client.requests.post", fake_post)

    answer = OllamaClient(settings).chat(
        [{"role": "user", "content": "Hi"}],
        options={
            "temperature": 0.25,
            "topP": 0.8,
            "maxTokens": 600,
            "contextWindow": 8192,
            "topKResults": 5,
        },
    )

    assert answer == "Local answer"
    assert captured["json"]["options"] == {
        "temperature": 0.25,
        "top_p": 0.8,
        "num_predict": 600,
        "num_ctx": 8192,
    }


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
