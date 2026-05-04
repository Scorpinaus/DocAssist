from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from backend.app.chat_client_factory import create_chat_client, normalize_chat_provider
from backend.app.config import Settings, settings as default_settings
from backend.app.doc_loader import available_versions
from backend.app.history_store import HistoryStore
from backend.app.ingest import ingest_version
from backend.app.models import (
    AskRequest,
    AskResponse,
    ChatProvidersResponse,
    HistoryResponse,
    IngestRequest,
    IngestResponse,
    Source,
    VersionsResponse,
)
from backend.app.ollama_client import OllamaClient
from backend.app.prompts import build_workspace_messages
from backend.app.retriever import Retriever
from backend.app.task_workspace import build_answer_workspace


_CHAT_PROVIDERS = ["ollama", "nanogpt"]


def create_app(
    settings: Settings = default_settings,
    retriever=None,
    ollama_client=None,
    chat_client=None,
    chat_clients=None,
    history_store=None,
) -> FastAPI:
    """Create and configure the FastAPI application.

    Optional retriever and model dependencies make the API easy to test without
    starting Chroma, Ollama, or a remote chat API.
    """
    app = FastAPI(title="DocAssist Java Documentation Agent")
    active_retriever = retriever or Retriever(settings)
    active_ollama = ollama_client or OllamaClient(settings)
    active_chat_clients = {"ollama": active_ollama}
    if chat_clients:
        active_chat_clients.update({normalize_chat_provider(name): client for name, client in chat_clients.items()})
    if chat_client:
        active_chat_clients[normalize_chat_provider(settings.chat_provider)] = chat_client
    elif ollama_client:
        active_chat_clients[normalize_chat_provider(settings.chat_provider)] = ollama_client
    active_history = history_store or HistoryStore(settings.history_db_path)

    @app.get("/api/health")
    def health():
        """Return a lightweight readiness response for local checks."""
        return {"status": "ok"}

    @app.get("/api/versions", response_model=VersionsResponse)
    def versions():
        """List available documentation versions and select a default."""
        versions = available_versions(settings.docs_dir)
        default = settings.default_version if settings.default_version in versions else (versions[0] if versions else "")
        return VersionsResponse(versions=versions, default=default)

    @app.get("/api/chat-providers", response_model=ChatProvidersResponse)
    def chat_providers():
        """List answer-generation providers and select the configured default."""
        default = normalize_chat_provider(settings.chat_provider)
        if default not in _CHAT_PROVIDERS:
            default = "ollama"
        return ChatProvidersResponse(providers=_CHAT_PROVIDERS, default=default)

    @app.post("/api/ingest", response_model=IngestResponse)
    def ingest(request: IngestRequest):
        """Rebuild the vector index for a selected documentation version."""
        _ensure_version_exists(settings, request.version)
        return IngestResponse(**ingest_version(settings, request.version, active_ollama))

    @app.post("/api/ask", response_model=AskResponse, response_model_exclude_none=True)
    def ask(request: AskRequest):
        """Answer a question using retrieved local documentation context."""
        _ensure_version_exists(settings, request.version)
        chunks = active_retriever.retrieve(request.version, request.query, settings.top_k_results)
        workspace = build_answer_workspace(request.version, request.query, chunks)
        messages = build_workspace_messages(workspace)
        provider = _selected_chat_provider(request.chatProvider, settings)
        active_chat = active_chat_clients.get(provider) or create_chat_client(settings, provider)
        answer = active_chat.chat(messages)
        sources = [
            Source(title=chunk.title, path=chunk.path, snippet=chunk.text[:500], score=chunk.score)
            for chunk in chunks
        ]
        active_history.add(
            version=request.version,
            question=request.query,
            answer=answer,
            sources=sources,
            workspace=workspace,
        )
        return AskResponse(
            answer=answer,
            sources=sources,
            workspace=workspace if request.includeWorkspace else None,
        )

    @app.get("/api/history", response_model=HistoryResponse)
    def history():
        """Return saved question history, newest first."""
        return HistoryResponse(history=active_history.list(settings.history_limit))

    @app.delete("/api/history")
    def clear_history():
        """Delete saved question history."""
        active_history.clear()
        return {"status": "ok"}

    if settings.frontend_dir.exists():
        app.mount("/static", StaticFiles(directory=settings.frontend_dir), name="static")

        @app.get("/")
        def index():
            """Serve the static frontend shell when it is present locally."""
            return FileResponse(settings.frontend_dir / "index.html")

        @app.get("/history")
        def history_page():
            """Serve the saved query history page."""
            return FileResponse(settings.frontend_dir / "history.html")

    return app


def _ensure_version_exists(settings: Settings, version: str) -> None:
    """Raise a 404 when a request references an unknown docs version."""
    if version not in available_versions(settings.docs_dir):
        raise HTTPException(status_code=404, detail=f"Documentation version not found: {version}")


def _selected_chat_provider(requested_provider: str | None, settings: Settings) -> str:
    """Return a supported provider name for one answer request."""
    provider = normalize_chat_provider(requested_provider or settings.chat_provider)
    if provider not in _CHAT_PROVIDERS:
        raise HTTPException(status_code=400, detail=f"Unsupported chat provider: {requested_provider}")
    return provider


app = create_app()
