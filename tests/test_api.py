from pathlib import Path

from fastapi.testclient import TestClient

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

    def chat(self, messages):
        self.prompt = messages[-1]["content"]
        return "Step 1: Implement Runnable.\nStep 2: Override run()."


def make_client(tmp_path: Path):
    docs_dir = tmp_path / "docs"
    (docs_dir / "jdk8").mkdir(parents=True)
    settings = Settings(docs_dir=docs_dir, indexes_dir=tmp_path / "indexes")
    retriever = FakeRetriever()
    ollama = FakeOllamaClient()
    app = create_app(settings=settings, retriever=retriever, ollama_client=ollama)
    return TestClient(app), retriever, ollama


def test_versions_returns_discovered_versions_and_default(tmp_path: Path):
    client, _, _ = make_client(tmp_path)

    response = client.get("/api/versions")

    assert response.status_code == 200
    assert response.json() == {"versions": ["jdk8"], "default": "jdk8"}


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
    assert retriever.calls == [("jdk8", "How do I run code in a thread?", 6)]
    assert "Target Java version: jdk8" in ollama.prompt
    assert "Temporary task workspace:" in ollama.prompt


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
    assert workspace["task"]["evidence"][0]["id"] == "E1"
    assert workspace["task"]["evidence"][0]["path"] == "api/java/lang/Runnable.html"


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
    settings = Settings(docs_dir=docs_dir, frontend_dir=frontend_dir, indexes_dir=tmp_path / "indexes")
    app = create_app(settings=settings, retriever=FakeRetriever(), ollama_client=FakeOllamaClient())
    client = TestClient(app)

    response = client.get("/history")

    assert response.status_code == 200
    assert "History" in response.text
