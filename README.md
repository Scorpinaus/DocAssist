# DocAssist Java Documentation Agent

DocAssist is a local retrieval-augmented generation (RAG) assistant for asking
questions against Java documentation stored under `docs/`. It is designed for
offline-friendly exploration of specific Java versions, with local embeddings,
local vector storage, and local chat completion through Ollama.

The first supported corpus is JDK 8 documentation under `docs/jdk8/`.

## Stack

- Python FastAPI backend
- Plain HTML/CSS/JS frontend
- Ollama local chat and embedding APIs
- ChromaDB local persistent indexes
- Pytest + FastAPI `TestClient` tests

The implementation follows the current official docs checked for FastAPI testing, Ollama `/api/chat` and `/api/embed`, and Chroma `PersistentClient`.

## Architecture

The main flow is:

```text
docs/<version>/ files
  -> backend.app.doc_loader.load_documents
  -> backend.app.chunker.chunk_documents
  -> Ollama /api/embed
  -> Chroma index under indexes/<version>/
  -> Retriever query
  -> prompt construction
  -> Ollama /api/chat
  -> FastAPI response and browser UI
```

Important boundaries:

- `backend/app/main.py` wires the FastAPI routes and dependency injection used by tests.
- `backend/app/doc_loader.py` discovers version folders and extracts visible text from HTML, Markdown, and text files.
- `backend/app/chunker.py` creates overlapping text chunks with citation metadata.
- `backend/app/ingest.py` orchestrates a full rebuild of one version index.
- `backend/app/vector_store.py` isolates all Chroma persistence details.
- `backend/app/retriever.py` embeds user queries and performs vector search.
- `backend/app/prompts.py` formats retrieved chunks into the chat prompt.
- `backend/app/ollama_client.py` is the HTTP boundary for Ollama.
- `frontend/` contains the static browser UI served by FastAPI.

For more design detail, see `docs/ARCHITECTURE.md`.

## Setup

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Install Ollama models:

```powershell
ollama pull qwen2.5-coder
ollama pull embeddinggemma
```

Put JDK 8 documentation files under:

```text
docs/jdk8/
```

## Ingest

```powershell
.\.venv\Scripts\python.exe -m backend.scripts.ingest_docs --version jdk8
```

The command reports progress as it works:

```text
Loading documents for jdk8 from ...
Loaded 2500 documents
Created 18000 chunks
Resetting vector index at ...
Embedding batch 1/563 (1-32 of 18000 chunks)
Embedding batch 2/563 (33-64 of 18000 chunks)
...
Finished ingestion for jdk8 in 1234.5s
```

## Run

For regular Windows use, run the launcher from File Explorer or PowerShell:

```powershell
.\run_docassist.bat
```

The launcher checks for `.venv`, confirms required Python packages are installed,
opens `http://127.0.0.1:8000`, and starts the FastAPI server. Keep the terminal
window open while using DocAssist. Press `Ctrl+C` in that window to stop it.

Ollama must already be running with the configured chat and embedding models
available.

For development, you can run the server directly:

```powershell
.\.venv\Scripts\python.exe -m uvicorn backend.app.main:app --reload
```

Open:

```text
http://127.0.0.1:8000
```

The app serves the static frontend from `frontend/` when that directory exists.
API routes remain available under `/api/...`.

## Test

```powershell
.\.venv\Scripts\python.exe -m pytest
```

The tests use fake Ollama and Chroma boundaries where practical, so they do not
require running local models for the core API and processing checks.

## Add More Java Versions

Create another docs folder and ingest it separately:

```text
docs/jdk17/
docs/jdk21/
```

Each version gets its own index under `indexes/`, so answers stay scoped to the selected Java version.

## Generated And Local Artifacts

- `docs/<version>/` contains local documentation corpora. Large downloaded docs
  are project data, not application source code.
- `indexes/<version>/` contains generated Chroma indexes and can be rebuilt by
  running ingestion again.
- `.venv/`, `__pycache__/`, pytest cache folders, and temporary test folders are
  local development artifacts.

## Troubleshooting

- If `/api/versions` returns an empty list, confirm that at least one directory
  exists below `docs/`, for example `docs/jdk8/`.
- If ingestion fails during embedding, confirm Ollama is running and the embed
  model from `backend/app/config.py` has been pulled.
- If asking a question returns no useful sources, ingest the selected version
  again and verify the source files contain readable HTML, Markdown, or text.
# DocAssist
