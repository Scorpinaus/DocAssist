from backend.app.chunker import chunk_documents
from backend.app.config import Settings
from backend.app.doc_loader import load_documents
from backend.app.ollama_client import OllamaClient
from backend.app.vector_store import VectorStore
from collections.abc import Callable
from time import perf_counter


def ingest_version(
    settings: Settings,
    version: str,
    ollama_client: OllamaClient | None = None,
    progress: Callable[[str], None] | None = None,
) -> dict:
    """Build a fresh vector index for one local documentation version.

    The ingestion pipeline loads source files, chunks their text, embeds each
    chunk with Ollama, and stores the embeddings in a version-scoped Chroma
    index. Re-ingesting resets the selected version so removed or changed source
    files do not leave stale chunks behind.
    """
    started_at = perf_counter()
    _report(progress, f"Loading documents for {version} from {settings.docs_dir / version}")
    documents = load_documents(settings.docs_dir, version)
    _report(progress, f"Loaded {len(documents)} documents")

    chunks = chunk_documents(
        documents,
        version=version,
        chunk_size=settings.chunk_size,
        overlap=settings.chunk_overlap,
    )
    _report(progress, f"Created {len(chunks)} chunks")

    ollama = ollama_client or OllamaClient(settings)
    vector_store = VectorStore(settings.indexes_dir)
    # Reset before writing so each ingest is an exact snapshot of the current
    # documentation folder, not an append-only update.
    _report(progress, f"Resetting vector index at {settings.indexes_dir / version}")
    vector_store.reset_version(version)

    total_batches = (len(chunks) + settings.batch_size - 1) // settings.batch_size
    for start in range(0, len(chunks), settings.batch_size):
        batch = chunks[start : start + settings.batch_size]
        batch_number = (start // settings.batch_size) + 1
        # Embedding in small batches keeps progress visible and avoids sending a
        # very large payload to the local Ollama server.
        _report(
            progress,
            f"Embedding batch {batch_number}/{total_batches} "
            f"({start + 1}-{start + len(batch)} of {len(chunks)} chunks)",
        )
        embeddings = ollama.embed([chunk.text for chunk in batch])
        vector_store.add_chunks(version, batch, embeddings)

    elapsed = perf_counter() - started_at
    _report(progress, f"Finished ingestion for {version} in {elapsed:.1f}s")

    return {
        "version": version,
        "documents": len(documents),
        "chunks": len(chunks),
        "indexPath": str(settings.indexes_dir / version),
    }


def _report(progress: Callable[[str], None] | None, message: str) -> None:
    """Send a progress message when the caller supplied a reporter callback."""
    if progress:
        progress(message)
