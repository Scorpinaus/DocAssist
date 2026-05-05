import json
from time import perf_counter

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from backend.app.chat_client_factory import create_chat_client, normalize_chat_provider
from backend.app.config import Settings, settings as default_settings
from backend.app.doc_loader import available_versions
from backend.app.errors import friendly_runtime_error, is_embedding_connection_error
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
from backend.app.query_workflow import answer_query, plan_query, prepare_synthesis, run_step
from backend.app.retriever import Retriever


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
        try:
            return IngestResponse(**ingest_version(settings, request.version, active_ollama))
        except Exception as error:
            if is_embedding_connection_error(error):
                raise HTTPException(status_code=503, detail=friendly_runtime_error(error, settings)) from error
            raise

    @app.post("/api/ask", response_model=AskResponse, response_model_exclude_none=True)
    def ask(request: AskRequest):
        """Answer a question using retrieved local documentation context."""
        _ensure_version_exists(settings, request.version)
        provider = _selected_chat_provider(request.chatProvider, settings)
        active_chat = active_chat_clients.get(provider) or create_chat_client(settings, provider)
        try:
            result = answer_query(settings, request.version, request.query, active_retriever, active_chat)
        except Exception as error:
            if is_embedding_connection_error(error):
                raise HTTPException(status_code=503, detail=friendly_runtime_error(error, settings)) from error
            raise
        active_history.add(
            version=request.version,
            question=request.query,
            answer=result.answer,
            sources=result.sources,
            workspace=result.workspace,
        )
        return AskResponse(
            answer=result.answer,
            sources=result.sources,
            workspace=result.workspace if request.includeWorkspace else None,
        )

    @app.post("/api/ask/events")
    def ask_events(request: AskRequest):
        """Stream backend progress events while answering a question."""
        _ensure_version_exists(settings, request.version)
        provider = _selected_chat_provider(request.chatProvider, settings)

        def stream_events():
            started_at = perf_counter()

            def elapsed_ms():
                return round((perf_counter() - started_at) * 1000, 1)

            def stage_event(stage: str, message: str, **extra):
                return _sse_event(
                    {
                        "type": "stage",
                        "stage": stage,
                        "message": message,
                        "elapsedMs": elapsed_ms(),
                        **extra,
                    }
                )

            def stage_complete_event(stage: str, stage_started_at: float, **extra):
                return _sse_event(
                    {
                        "type": "stage_complete",
                        "stage": stage,
                        "durationMs": round((perf_counter() - stage_started_at) * 1000, 1),
                        "elapsedMs": elapsed_ms(),
                        **extra,
                    }
                )

            try:
                stage_started_at = perf_counter()
                yield stage_event("prepare", "Preparing question...")
                yield stage_complete_event("prepare", stage_started_at)

                stage_started_at = perf_counter()
                yield stage_event("plan", "Planning multi-step retrieval...")
                active_chat = active_chat_clients.get(provider) or create_chat_client(settings, provider)
                plan = plan_query(settings, request.version, request.query, active_chat)
                yield stage_complete_event(
                    "plan",
                    stage_started_at,
                    steps=len(plan.steps),
                    plannerMode=plan.planner_mode,
                )

                step_runs = []
                for step in plan.steps:
                    stage_started_at = perf_counter()
                    yield stage_event(
                        "step",
                        f"Running step {step.id}: {step.title}...",
                        stepId=step.id,
                        stepTitle=step.title,
                    )
                    step_run = run_step(active_retriever, request.version, step, settings.top_k_results)
                    step_runs.append(step_run)
                    yield stage_event(
                        "step_retrieve",
                        f"Step {step.id} evidence retrieved.",
                        stepId=step.id,
                        sources=len(step_run.chunks),
                    )
                    yield stage_complete_event(
                        "step",
                        stage_started_at,
                        stepId=step.id,
                        sources=len(step_run.chunks),
                        status=step_run.step.status,
                    )

                stage_started_at = perf_counter()
                yield stage_event("synthesize", "Synthesizing final answer...")
                synthesis = prepare_synthesis(
                    request.version,
                    request.query,
                    step_runs,
                    planner_mode=plan.planner_mode,
                )
                yield stage_complete_event("synthesize", stage_started_at)

                stage_started_at = perf_counter()
                yield stage_event("answer", f"Asking {_chat_provider_label(provider)}...")
                answer = active_chat.chat(synthesis.messages)
                yield stage_complete_event("answer", stage_started_at)
                active_history.add(
                    version=request.version,
                    question=request.query,
                    answer=answer,
                    sources=synthesis.sources,
                    workspace=synthesis.workspace,
                )
                yield _sse_event(
                    {
                        "type": "complete",
                        "answer": answer,
                        "sources": [source.model_dump(mode="json") for source in synthesis.sources],
                        "workspace": synthesis.workspace.model_dump(mode="json") if request.includeWorkspace else None,
                        "totalMs": elapsed_ms(),
                    }
                )
            except Exception as error:
                yield _sse_event({"type": "error", "message": friendly_runtime_error(error, settings)})

        return StreamingResponse(
            stream_events(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
            },
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


def _chat_provider_label(provider: str) -> str:
    """Return a display label for backend progress events."""
    if provider == "nanogpt":
        return "NanoGPT"
    if provider == "ollama":
        return "Ollama"
    return provider


def _sse_event(payload: dict) -> str:
    """Format one Server-Sent Event data frame."""
    return f"data: {json.dumps(payload)}\n\n"


app = create_app()
