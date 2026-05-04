from pathlib import Path

from backend.app.config import Settings
from backend.app.ingest import ingest_version


class FakeOllama:
    def embed(self, inputs):
        return [[0.1, 0.2, 0.3] for _ in inputs]


class FakeVectorStore:
    reset_versions = []
    added_batches = []

    def __init__(self, indexes_dir):
        self.indexes_dir = indexes_dir

    def reset_version(self, version):
        self.reset_versions.append(version)

    def add_chunks(self, version, chunks, embeddings):
        self.added_batches.append((version, len(chunks), len(embeddings)))


def test_ingest_version_reports_progress(tmp_path: Path, monkeypatch):
    docs_dir = tmp_path / "docs" / "jdk8"
    docs_dir.mkdir(parents=True)
    for index in range(3):
        (docs_dir / f"page-{index}.html").write_text(
            f"<html><head><title>Page {index}</title></head><body>{'Java docs ' * 80}</body></html>",
            encoding="utf-8",
        )
    settings = Settings(
        docs_dir=tmp_path / "docs",
        indexes_dir=tmp_path / "indexes",
        batch_size=2,
        chunk_size=200,
        chunk_overlap=20,
    )
    messages = []

    FakeVectorStore.reset_versions = []
    FakeVectorStore.added_batches = []
    monkeypatch.setattr("backend.app.ingest.VectorStore", FakeVectorStore)

    summary = ingest_version(settings, "jdk8", ollama_client=FakeOllama(), progress=messages.append)

    assert summary["documents"] == 3
    assert summary["chunks"] > 3
    assert FakeVectorStore.reset_versions == ["jdk8"]
    assert any("Loading documents for jdk8" in message for message in messages)
    assert any("Loaded 3 documents" in message for message in messages)
    assert any("Created" in message and "chunks" in message for message in messages)
    assert any("Embedding batch 1/" in message for message in messages)
    assert any("Finished ingestion for jdk8" in message for message in messages)
