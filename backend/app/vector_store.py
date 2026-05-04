from pathlib import Path
import hashlib

import chromadb

from backend.app.models import DocumentChunk, RetrievedChunk


class VectorStore:
    """Persistence boundary for version-scoped Chroma vector indexes."""

    def __init__(self, indexes_dir: Path):
        """Store the root directory used for all Chroma indexes."""
        self.indexes_dir = indexes_dir

    def reset_version(self, version: str) -> None:
        """Delete the existing collection for a version if it exists."""
        client = self._client(version)
        try:
            client.delete_collection("java_docs")
        except Exception:
            # Chroma raises when the collection does not exist; reset should be
            # idempotent because callers use it before every full ingest.
            pass

    def add_chunks(self, version: str, chunks: list[DocumentChunk], embeddings: list[list[float]]) -> None:
        """Persist document chunks and their matching embeddings."""
        if len(chunks) != len(embeddings):
            raise ValueError("chunks and embeddings must have the same length")

        collection = self._collection(version)
        collection.add(
            ids=[_chunk_id(chunk) for chunk in chunks],
            documents=[chunk.text for chunk in chunks],
            metadatas=[chunk.metadata for chunk in chunks],
            embeddings=embeddings,
        )

    def query(self, version: str, query_embedding: list[float], top_k: int) -> list[RetrievedChunk]:
        """Query one version index and map Chroma results to app models."""
        collection = self._collection(version)
        result = collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
            include=["documents", "metadatas", "distances"],
        )
        documents = result.get("documents", [[]])[0]
        metadatas = result.get("metadatas", [[]])[0]
        distances = result.get("distances", [[]])[0]

        chunks: list[RetrievedChunk] = []
        for document, metadata, distance in zip(documents, metadatas, distances):
            chunks.append(
                RetrievedChunk(
                    text=document,
                    title=str(metadata.get("title", "")),
                    path=str(metadata.get("source_path", "")),
                    # With cosine distance, smaller is better. The app exposes
                    # a simple similarity-like score for display and tests.
                    score=1.0 - float(distance) if distance is not None else None,
                )
            )
        return chunks

    def _client(self, version: str):
        """Create a Chroma client rooted at the selected version index path."""
        path = self.indexes_dir / version
        path.mkdir(parents=True, exist_ok=True)
        return chromadb.PersistentClient(path=str(path))

    def _collection(self, version: str):
        """Return the shared Java docs collection for a version index."""
        return self._client(version).get_or_create_collection(
            name="java_docs",
            metadata={"hnsw:space": "cosine"},
        )


def _chunk_id(chunk: DocumentChunk) -> str:
    """Create a stable Chroma id from source metadata and chunk text."""
    key = f"{chunk.metadata.get('source_path')}:{chunk.metadata.get('chunk_index')}:{chunk.text}"
    return hashlib.sha1(key.encode("utf-8")).hexdigest()
