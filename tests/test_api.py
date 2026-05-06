from pathlib import Path
import json
import sqlite3

from fastapi.testclient import TestClient
import requests

from backend.app.config import Settings
from backend.app.main import create_app
from backend.app.models import RetrievedChunk


class FakeRetriever:
    def __init__(self):
        self.calls = []

    def retrieve(self, version: str, query: str, top_k: int):
        self.calls.append((version, query, top_k))
        return [
            RetrievedChunk(
                text="The Runnable interface should be implemented by any class whose instances are intended to be executed by a thread.",
                title="Runnable",
                path="api/java/lang/Runnable.html",
                score=0.91,
            )
        ]


class FakeOllamaClient:
    def __init__(self):
        self.prompt = ""
        self.calls = 0
        self.options = None

    def chat(self, messages, options=None):
        self.calls += 1
        self.prompt = messages[-1]["content"]
        self.options = options
        return "Step 1: Implement Runnable.\nStep 2: Override run()."


class FakeNanoGPTClient:
    def __init__(self):
        self.prompt = ""
        self.calls = 0
        self.options = None

    def chat(self, messages, options=None):
        self.calls += 1
        self.prompt = messages[-1]["content"]
        self.options = options
        return "NanoGPT answer."


class FakePlannerAnswerClient:
    def __init__(self, planner_response: str):
        self.planner_response = planner_response
        self.prompts = []
        self.options = []

    def chat(self, messages, options=None):
        prompt = messages[-1]["content"]
        self.prompts.append(prompt)
        self.options.append(options)
        if "Return only valid JSON" in prompt:
            return self.planner_response
        return "Model-planned answer."


class OfflineEmbeddingRetriever:
    def retrieve(self, version: str, query: str, top_k: int):
        raise requests.ConnectionError("Connection refused")


class OfflineEmbeddingClient:
    def chat(self, messages, options=None):
        return "Unused answer."

    def embed(self, inputs):
        raise requests.ConnectionError("Connection refused")


def sse_payloads(response):
    payloads = []
    for line in response.text.splitlines():
        if line.startswith("data: "):
            payloads.append(json.loads(line.removeprefix("data: ")))
    return payloads


def make_client(tmp_path: Path):
    docs_dir = tmp_path / "docs"
    (docs_dir / "jdk8").mkdir(parents=True, exist_ok=True)
    settings = Settings(
        docs_dir=docs_dir,
        indexes_dir=tmp_path / "indexes",
        history_db_path=tmp_path / "history.sqlite3",
        chat_provider="ollama",
    )
    retriever = FakeRetriever()
    ollama = FakeOllamaClient()
    app = create_app(settings=settings, retriever=retriever, ollama_client=ollama)
    return TestClient(app), retriever, ollama


def test_versions_returns_discovered_versions_and_default(tmp_path: Path):
    client, _, _ = make_client(tmp_path)

    response = client.get("/api/versions")

    assert response.status_code == 200
    assert response.json() == {"versions": ["jdk8"], "default": "jdk8"}


def test_chat_providers_returns_available_providers_and_default(tmp_path: Path):
    client, _, _ = make_client(tmp_path)

    response = client.get("/api/chat-providers")

    assert response.status_code == 200
    assert response.json() == {"providers": ["ollama", "nanogpt"], "default": "ollama"}


def test_ask_uses_selected_version_and_returns_sources(tmp_path: Path):
    client, retriever, ollama = make_client(tmp_path)

    response = client.post(
        "/api/ask",
        json={"version": "jdk8", "query": "How do I run code in a thread?"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["answer"].startswith("Step 1")
    assert payload["sources"][0]["path"] == "api/java/lang/Runnable.html"
    assert "workspace" not in payload
    assert [call[1] for call in retriever.calls] == [
        "How do I run code in a thread?",
        "How do I run code in a thread? API classes methods behavior",
        "How do I run code in a thread? examples constraints exceptions",
    ]
    assert "Target Java version: jdk8" in ollama.prompt
    assert "Temporary task workspace:" in ollama.prompt
    assert "Multi-step task plan:" in ollama.prompt


def test_ask_can_use_nanogpt_provider_for_one_request(tmp_path: Path):
    docs_dir = tmp_path / "docs"
    (docs_dir / "jdk8").mkdir(parents=True, exist_ok=True)
    settings = Settings(
        docs_dir=docs_dir,
        indexes_dir=tmp_path / "indexes",
        history_db_path=tmp_path / "history.sqlite3",
        chat_provider="ollama",
    )
    retriever = FakeRetriever()
    ollama = FakeOllamaClient()
    nanogpt = FakeNanoGPTClient()
    app = create_app(
        settings=settings,
        retriever=retriever,
        ollama_client=ollama,
        chat_clients={"nanogpt": nanogpt},
    )
    client = TestClient(app)

    response = client.post(
        "/api/ask",
        json={
            "version": "jdk8",
            "query": "How do I run code in a thread?",
            "chatProvider": "nanogpt",
        },
    )

    assert response.status_code == 200
    assert response.json()["answer"] == "NanoGPT answer."
    assert nanogpt.calls == 1
    assert ollama.calls == 0


def test_ask_applies_generation_options_and_retrieval_top_k(tmp_path: Path):
    client, retriever, ollama = make_client(tmp_path)

    response = client.post(
        "/api/ask",
        json={
            "version": "jdk8",
            "query": "How do I run code in a thread?",
            "options": {
                "temperature": 0.35,
                "topP": 0.9,
                "maxTokens": 700,
                "frequencyPenalty": 0.1,
                "presencePenalty": 0.0,
                "reasoningEffort": "medium",
                "contextWindow": 8192,
                "topKResults": 4,
            },
        },
    )

    assert response.status_code == 200
    assert [call[2] for call in retriever.calls] == [4, 4, 4]
    assert ollama.options.model_dump(exclude_none=True, by_alias=True) == {
        "temperature": 0.35,
        "topP": 0.9,
        "maxTokens": 700,
        "frequencyPenalty": 0.1,
        "presencePenalty": 0.0,
        "reasoningEffort": "medium",
        "contextWindow": 8192,
        "topKResults": 4,
    }


def test_ask_rejects_unknown_chat_provider(tmp_path: Path):
    client, _, _ = make_client(tmp_path)

    response = client.post(
        "/api/ask",
        json={
            "version": "jdk8",
            "query": "How do I run code in a thread?",
            "chatProvider": "unknown",
        },
    )

    assert response.status_code == 400
    assert "Unsupported chat provider" in response.json()["detail"]


def test_ask_returns_friendly_embedding_error_when_ollama_is_offline(tmp_path: Path):
    docs_dir = tmp_path / "docs"
    (docs_dir / "jdk8").mkdir(parents=True, exist_ok=True)
    settings = Settings(
        docs_dir=docs_dir,
        indexes_dir=tmp_path / "indexes",
        history_db_path=tmp_path / "history.sqlite3",
        chat_provider="nanogpt",
    )
    app = create_app(
        settings=settings,
        retriever=OfflineEmbeddingRetriever(),
        chat_clients={"nanogpt": FakeNanoGPTClient()},
    )
    client = TestClient(app)

    response = client.post(
        "/api/ask",
        json={
            "version": "jdk8",
            "query": "How do I filter a list?",
            "chatProvider": "nanogpt",
        },
    )

    assert response.status_code == 503
    assert response.json()["detail"] == (
        "Ollama embeddings are unavailable at http://localhost:11434. "
        "Start Ollama, make sure the embedding model 'embeddinggemma' is installed, then retry."
    )


def test_ask_events_streams_backend_stages_and_complete_payload(tmp_path: Path):
    client, retriever, ollama = make_client(tmp_path)

    response = client.post(
        "/api/ask/events",
        json={
            "version": "jdk8",
            "query": "How do I run code in a thread?",
            "chatProvider": "ollama",
            "includeWorkspace": True,
        },
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    payloads = sse_payloads(response)
    stage_messages = [payload["message"] for payload in payloads if payload["type"] == "stage"]
    assert stage_messages == [
        "Preparing question...",
        "Planning multi-step retrieval...",
        "Running step S1: Identify the documentation topic...",
        "Step S1 evidence retrieved.",
        "Running step S2: Gather API details...",
        "Step S2 evidence retrieved.",
        "Running step S3: Check usage constraints and examples...",
        "Step S3 evidence retrieved.",
        "Synthesizing final answer...",
        "Asking Ollama...",
    ]
    stage_payloads = [payload for payload in payloads if payload["type"] == "stage"]
    stage_complete_payloads = [payload for payload in payloads if payload["type"] == "stage_complete"]
    assert [payload["stage"] for payload in stage_payloads] == [
        "prepare",
        "plan",
        "step",
        "step_retrieve",
        "step",
        "step_retrieve",
        "step",
        "step_retrieve",
        "synthesize",
        "answer",
    ]
    assert [payload["stage"] for payload in stage_complete_payloads] == [
        "prepare",
        "plan",
        "step",
        "step",
        "step",
        "synthesize",
        "answer",
    ]
    assert all(isinstance(payload["elapsedMs"], int | float) for payload in stage_payloads)
    assert all(payload["elapsedMs"] >= 0 for payload in stage_payloads)
    assert all(isinstance(payload["durationMs"], int | float) for payload in stage_complete_payloads)
    assert all(payload["durationMs"] >= 0 for payload in stage_complete_payloads)
    step_complete_payloads = [payload for payload in stage_complete_payloads if payload["stage"] == "step"]
    assert [payload["stepId"] for payload in step_complete_payloads] == ["S1", "S2", "S3"]
    assert all(payload["sources"] == 1 for payload in step_complete_payloads)
    complete = payloads[-1]
    assert complete["type"] == "complete"
    assert isinstance(complete["totalMs"], int | float)
    assert complete["totalMs"] >= 0
    assert complete["answer"].startswith("Step 1")
    assert complete["sources"][0]["path"] == "api/java/lang/Runnable.html"
    assert complete["workspace"]["task"]["evidence"][0]["id"] == "E1"
    assert [step["id"] for step in complete["workspace"]["task"]["steps"]] == ["S1", "S2", "S3"]
    assert complete["workspace"]["task"]["steps"][0]["evidence"][0]["id"] == "E1"
    assert [call[1] for call in retriever.calls] == [
        "How do I run code in a thread?",
        "How do I run code in a thread? API classes methods behavior",
        "How do I run code in a thread? examples constraints exceptions",
    ]
    assert ollama.calls == 1


def test_ask_events_uses_nanogpt_provider_stage_and_client(tmp_path: Path):
    docs_dir = tmp_path / "docs"
    (docs_dir / "jdk8").mkdir(parents=True, exist_ok=True)
    settings = Settings(
        docs_dir=docs_dir,
        indexes_dir=tmp_path / "indexes",
        history_db_path=tmp_path / "history.sqlite3",
        chat_provider="ollama",
    )
    retriever = FakeRetriever()
    ollama = FakeOllamaClient()
    nanogpt = FakeNanoGPTClient()
    app = create_app(
        settings=settings,
        retriever=retriever,
        ollama_client=ollama,
        chat_clients={"nanogpt": nanogpt},
    )
    client = TestClient(app)

    response = client.post(
        "/api/ask/events",
        json={
            "version": "jdk8",
            "query": "How do I run code in a thread?",
            "chatProvider": "nanogpt",
        },
    )

    assert response.status_code == 200
    payloads = sse_payloads(response)
    stage_messages = [payload["message"] for payload in payloads if payload["type"] == "stage"]
    assert "Asking NanoGPT..." in stage_messages
    assert payloads[-1]["answer"] == "NanoGPT answer."
    assert nanogpt.calls == 1
    assert ollama.calls == 0


def test_ask_events_applies_generation_options_and_retrieval_top_k(tmp_path: Path):
    client, retriever, ollama = make_client(tmp_path)

    response = client.post(
        "/api/ask/events",
        json={
            "version": "jdk8",
            "query": "How do I run code in a thread?",
            "options": {
                "temperature": 0.1,
                "contextWindow": 4096,
                "topKResults": 2,
            },
        },
    )

    assert response.status_code == 200
    assert [call[2] for call in retriever.calls] == [2, 2, 2]
    assert ollama.options.model_dump(exclude_none=True, by_alias=True) == {
        "temperature": 0.1,
        "contextWindow": 4096,
        "topKResults": 2,
    }


def test_ask_events_streams_model_planner_metadata(tmp_path: Path):
    docs_dir = tmp_path / "docs"
    (docs_dir / "jdk8").mkdir(parents=True, exist_ok=True)
    settings = Settings(
        docs_dir=docs_dir,
        indexes_dir=tmp_path / "indexes",
        history_db_path=tmp_path / "history.sqlite3",
        chat_provider="ollama",
        query_planner="model",
    )
    retriever = FakeRetriever()
    client = FakePlannerAnswerClient(
        """
        {
          "steps": [
            {
              "title": "Find Runnable",
              "description": "Look up Runnable documentation.",
              "retrievalQuery": "Runnable interface"
            }
          ]
        }
        """
    )
    app = create_app(settings=settings, retriever=retriever, ollama_client=client)
    test_client = TestClient(app)

    response = test_client.post(
        "/api/ask/events",
        json={
            "version": "jdk8",
            "query": "How do I run code in a thread?",
            "includeWorkspace": True,
        },
    )

    assert response.status_code == 200
    payloads = sse_payloads(response)
    plan_complete = next(payload for payload in payloads if payload["type"] == "stage_complete" and payload["stage"] == "plan")
    complete = payloads[-1]
    assert plan_complete["plannerMode"] == "model"
    assert plan_complete["steps"] == 1
    assert complete["workspace"]["task"]["plannerMode"] == "model"
    assert complete["workspace"]["task"]["steps"][0]["retrievalQuery"] == "Runnable interface"


def test_ask_events_rejects_unknown_chat_provider(tmp_path: Path):
    client, _, _ = make_client(tmp_path)

    response = client.post(
        "/api/ask/events",
        json={
            "version": "jdk8",
            "query": "How do I run code in a thread?",
            "chatProvider": "unknown",
        },
    )

    assert response.status_code == 400
    assert "Unsupported chat provider" in response.json()["detail"]


def test_ask_events_streams_friendly_embedding_error_when_ollama_is_offline(tmp_path: Path):
    docs_dir = tmp_path / "docs"
    (docs_dir / "jdk8").mkdir(parents=True, exist_ok=True)
    settings = Settings(
        docs_dir=docs_dir,
        indexes_dir=tmp_path / "indexes",
        history_db_path=tmp_path / "history.sqlite3",
        chat_provider="nanogpt",
    )
    app = create_app(
        settings=settings,
        retriever=OfflineEmbeddingRetriever(),
        chat_clients={"nanogpt": FakeNanoGPTClient()},
    )
    client = TestClient(app)

    response = client.post(
        "/api/ask/events",
        json={
            "version": "jdk8",
            "query": "How do I filter a list?",
            "chatProvider": "nanogpt",
        },
    )

    assert response.status_code == 200
    payloads = sse_payloads(response)
    assert payloads[-1] == {
        "type": "error",
        "message": (
            "Ollama embeddings are unavailable at http://localhost:11434. "
            "Start Ollama, make sure the embedding model 'embeddinggemma' is installed, then retry."
        ),
    }


def test_ask_can_return_temporary_workspace_when_requested(tmp_path: Path):
    client, _, _ = make_client(tmp_path)

    response = client.post(
        "/api/ask",
        json={
            "version": "jdk8",
            "query": "How do I run code in a thread?",
            "includeWorkspace": True,
        },
    )

    assert response.status_code == 200
    workspace = response.json()["workspace"]
    assert workspace["task"]["version"] == "jdk8"
    assert workspace["task"]["plannerMode"] == "deterministic"
    assert workspace["task"]["evidence"][0]["id"] == "E1"
    assert workspace["task"]["evidence"][0]["path"] == "api/java/lang/Runnable.html"


def test_ask_uses_model_planner_when_enabled(tmp_path: Path):
    docs_dir = tmp_path / "docs"
    (docs_dir / "jdk8").mkdir(parents=True, exist_ok=True)
    settings = Settings(
        docs_dir=docs_dir,
        indexes_dir=tmp_path / "indexes",
        history_db_path=tmp_path / "history.sqlite3",
        chat_provider="ollama",
        query_planner="model",
    )
    retriever = FakeRetriever()
    client = FakePlannerAnswerClient(
        """
        {
          "steps": [
            {
              "title": "Find Runnable",
              "description": "Look up Runnable documentation.",
              "retrievalQuery": "Runnable interface"
            },
            {
              "title": "Find Thread start",
              "description": "Look up Thread start behavior.",
              "retrievalQuery": "Thread start Runnable"
            }
          ]
        }
        """
    )
    app = create_app(settings=settings, retriever=retriever, ollama_client=client)
    test_client = TestClient(app)

    response = test_client.post(
        "/api/ask",
        json={
            "version": "jdk8",
            "query": "How do I run code in a thread?",
            "includeWorkspace": True,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["answer"] == "Model-planned answer."
    assert payload["workspace"]["task"]["plannerMode"] == "model"
    assert [step["title"] for step in payload["workspace"]["task"]["steps"]] == [
        "Find Runnable",
        "Find Thread start",
    ]
    assert [call[1] for call in retriever.calls] == ["Runnable interface", "Thread start Runnable"]
    assert len(client.prompts) == 2


def test_ask_saves_query_history(tmp_path: Path):
    client, _, _ = make_client(tmp_path)

    response = client.post(
        "/api/ask",
        json={
            "version": "jdk8",
            "query": "How do I run code in a thread?",
            "includeWorkspace": True,
        },
    )
    history_response = client.get("/api/history")

    assert response.status_code == 200
    assert history_response.status_code == 200
    history = history_response.json()["history"]
    assert len(history) == 1
    assert history[0]["version"] == "jdk8"
    assert history[0]["question"] == "How do I run code in a thread?"
    assert history[0]["answer"].startswith("Step 1")
    assert history[0]["sources"][0]["path"] == "api/java/lang/Runnable.html"
    assert history[0]["workspace"]["task"]["evidence"][0]["id"] == "E1"


def test_history_loads_legacy_string_workspace_steps(tmp_path: Path):
    client, _, _ = make_client(tmp_path)
    db_path = tmp_path / "history.sqlite3"
    legacy_workspace = {
        "task": {
            "version": "jdk8",
            "query": "How do I run code in a thread?",
            "intent": "Answer the user's Java documentation question.",
            "plannerMode": "deterministic",
            "steps": [
                "Identify the Java documentation topic requested by the user.",
                "Cite the source filenames used in the answer.",
            ],
            "evidence": [],
            "gaps": [],
        }
    }

    with sqlite3.connect(db_path) as connection:
        connection.execute(
            """
            INSERT INTO query_history (
                id,
                created_at,
                version,
                question,
                answer,
                sources_json,
                workspace_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "legacy",
                "2026-05-06T00:00:00+00:00",
                "jdk8",
                "How do I run code in a thread?",
                "Use Runnable.",
                "[]",
                json.dumps(legacy_workspace),
            ),
        )

    response = client.get("/api/history")

    assert response.status_code == 200
    steps = response.json()["history"][0]["workspace"]["task"]["steps"]
    assert steps[0]["id"] == "S1"
    assert steps[0]["description"] == "Identify the Java documentation topic requested by the user."
    assert steps[0]["retrievalQuery"] == "How do I run code in a thread?"
    assert steps[1]["title"] == "Cite the source filenames used in the answer."


def test_ingest_returns_friendly_embedding_error_when_ollama_is_offline(tmp_path: Path):
    docs_dir = tmp_path / "docs" / "jdk8"
    docs_dir.mkdir(parents=True, exist_ok=True)
    (docs_dir / "page.html").write_text(
        f"<html><head><title>Streams</title></head><body>{'Java streams documentation. ' * 80}</body></html>",
        encoding="utf-8",
    )
    settings = Settings(
        docs_dir=tmp_path / "docs",
        indexes_dir=tmp_path / "indexes",
        history_db_path=tmp_path / "history.sqlite3",
    )
    app = create_app(settings=settings, ollama_client=OfflineEmbeddingClient())
    client = TestClient(app)

    response = client.post("/api/ingest", json={"version": "jdk8"})

    assert response.status_code == 503
    assert response.json()["detail"] == (
        "Ollama embeddings are unavailable at http://localhost:11434. "
        "Start Ollama, make sure the embedding model 'embeddinggemma' is installed, then retry."
    )


def test_history_can_be_cleared(tmp_path: Path):
    client, _, _ = make_client(tmp_path)
    client.post(
        "/api/ask",
        json={"version": "jdk8", "query": "How do I run code in a thread?"},
    )

    response = client.delete("/api/history")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert client.get("/api/history").json() == {"history": []}


def test_history_persists_across_app_instances(tmp_path: Path):
    client, _, _ = make_client(tmp_path)
    client.post(
        "/api/ask",
        json={"version": "jdk8", "query": "How do I run code in a thread?"},
    )

    second_client, _, _ = make_client(tmp_path)
    history = second_client.get("/api/history").json()["history"]

    assert len(history) == 1
    assert history[0]["question"] == "How do I run code in a thread?"


def test_ask_rejects_unknown_version(tmp_path: Path):
    client, _, _ = make_client(tmp_path)

    response = client.post(
        "/api/ask",
        json={"version": "jdk17", "query": "What is a record?"},
    )

    assert response.status_code == 404
    assert "Documentation version not found" in response.json()["detail"]


def test_history_page_is_served_when_frontend_exists(tmp_path: Path):
    frontend_dir = tmp_path / "frontend"
    frontend_dir.mkdir()
    (frontend_dir / "index.html").write_text("<h1>Ask</h1>", encoding="utf-8")
    (frontend_dir / "history.html").write_text("<h1>History</h1>", encoding="utf-8")
    docs_dir = tmp_path / "docs"
    (docs_dir / "jdk8").mkdir(parents=True)
    settings = Settings(
        docs_dir=docs_dir,
        frontend_dir=frontend_dir,
        indexes_dir=tmp_path / "indexes",
        history_db_path=tmp_path / "history.sqlite3",
    )
    app = create_app(settings=settings, retriever=FakeRetriever(), ollama_client=FakeOllamaClient())
    client = TestClient(app)

    response = client.get("/history")

    assert response.status_code == 200
    assert "History" in response.text
