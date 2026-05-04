from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from backend.app.config import Settings, settings as default_settings
from backend.app.doc_loader import available_versions
from backend.app.ingest import ingest_version
from backend.app.models import AskRequest, AskResponse, IngestRequest, IngestResponse, Source, VersionsResponse
from backend.app.ollama_client import OllamaClient
from backend.app.prompts import build_workspace_messages
from backend.app.retriever import Retriever
from backend.app.task_workspace import build_answer_workspace


def create_app(
    settings: Settings = default_settings,
    retriever=None,
    ollama_client=None,
) -> FastAPI:
    """Create and configure the FastAPI application.

    Optional retriever and Ollama dependencies make the API easy to test without
    starting Chroma or Ollama.
    """
    app = FastAPI(title="DocAssist Java Documentation Agent")
    active_retriever = retriever or Retriever(settings)
    active_ollama = ollama_client or OllamaClient(settings)

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
        answer = active_ollama.chat(messages)
        return AskResponse(
            answer=answer,
            sources=[
                Source(title=chunk.title, path=chunk.path, snippet=chunk.text[:500], score=chunk.score)
                for chunk in chunks
            ],
            workspace=workspace if request.includeWorkspace else None,
        )

    if settings.frontend_dir.exists():
        app.mount("/static", StaticFiles(directory=settings.frontend_dir), name="static")

        @app.get("/")
        def index():
            """Serve the static frontend shell when it is present locally."""
            return FileResponse(settings.frontend_dir / "index.html")

    return app


def _ensure_version_exists(settings: Settings, version: str) -> None:
    """Raise a 404 when a request references an unknown docs version."""
    if version not in available_versions(settings.docs_dir):
        raise HTTPException(status_code=404, detail=f"Documentation version not found: {version}")


app = create_app()
