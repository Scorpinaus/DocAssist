# DocAssist Java Documentation Agent

DocAssist is a retrieval-augmented generation (RAG) assistant for asking
questions against Java documentation stored under `docs/`. It is designed for
offline-friendly exploration of specific Java versions, with local embeddings
and local vector storage. Answer generation uses Ollama by default, or an
optional OpenAI-compatible chat API when configured.

The first supported corpus is JDK 8 documentation under `docs/jdk8/`.

## Stack

- Python FastAPI backend
- Plain HTML/CSS/JS frontend
- Ollama local chat and embedding APIs
- Optional OpenAI-compatible chat completion API
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
  -> configured chat provider
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
- `backend/app/api_chat_client.py` is the HTTP boundary for optional remote chat APIs.
- `backend/app/chat_client_factory.py` selects the configured chat provider.
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

Documentation can be either expanded files and folders or Java documentation
archives. For example, both of these are supported:

```text
docs/jdk8/api/java/util/List.html
docs/jdk8/jdk8-docs.jar
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

### Optional NanoGPT API Chat

Embeddings always come from Ollama, including during ingestion and retrieval.
To use NanoGPT for answer generation only, edit:

```text
data/local_settings.json
```

Use this shape:

```json
{
  "chat_provider": "nanogpt",
  "api_chat_model": "deepseek/deepseek-v4-flash",
  "api_chat_base_url": "https://nano-gpt.com/api/v1",
  "llm_api_key": "your-api-key"
}
```

The API key can be added later. Until `llm_api_key` is set, DocAssist will
report that the key is missing when you ask a question with API chat enabled.

By default, API chat requests stream from:

```text
https://nano-gpt.com/api/v1/chat/completions
```

For another OpenAI-compatible provider, set a custom base URL:

```powershell
$env:DOCASSIST_API_CHAT_BASE_URL="https://provider.example/v1"
```

To return to fully local answer generation:

```json
{
  "chat_provider": "ollama",
  "api_chat_model": "deepseek/deepseek-v4-flash",
  "api_chat_base_url": "https://nano-gpt.com/api/v1",
  "llm_api_key": ""
}
```

### Ask Options

The Ask screen includes per-query controls for generation and retrieval:

- `temperature` controls sampling randomness.
- `top_p` controls nucleus sampling where the selected provider supports it.
- `max_tokens` caps generated answer length.
- `frequency_penalty` and `presence_penalty` are sent to OpenAI-compatible providers such as NanoGPT.
- `reasoning_effort` is sent to reasoning-capable NanoGPT/OpenAI-compatible models.
- `context_window` maps to Ollama `num_ctx`; NanoGPT's similarly named context-memory setting does not expand the target model context window, so DocAssist does not send it for NanoGPT.
- `top_k_results` controls how many retrieved documentation chunks each query step uses.

You can set defaults in `data/local_settings.json`:

```json
{
  "generation_temperature": 0.2,
  "generation_top_p": 0.9,
  "generation_max_tokens": 900,
  "generation_frequency_penalty": 0.1,
  "generation_presence_penalty": 0.0,
  "generation_reasoning_effort": "medium",
  "generation_context_window": 8192,
  "top_k_results": 6
}
```

Per-query browser selections override these defaults for that request.

### Optional Model-Assisted Query Planning

DocAssist uses deterministic multi-step retrieval planning by default. To let
the configured chat model draft the retrieval steps for each question, set:

```json
{
  "query_planner": "model"
}
```

If the model planner returns invalid JSON or incomplete steps, DocAssist falls
back to deterministic planning for that request.

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
  are project data, not application source code. The loader supports expanded
  HTML, Markdown, and text files, plus documentation packaged as `.jar` files.
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
