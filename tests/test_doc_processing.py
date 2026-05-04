from pathlib import Path
from zipfile import ZipFile

from backend.app.chunker import chunk_document
from backend.app.doc_loader import load_documents


def test_load_documents_extracts_title_and_visible_text(tmp_path: Path):
    docs_dir = tmp_path / "docs" / "jdk8"
    docs_dir.mkdir(parents=True)
    page = docs_dir / "api" / "java" / "util" / "List.html"
    page.parent.mkdir(parents=True)
    page.write_text(
        """
        <html>
          <head><title>List (Java Platform SE 8)</title><script>ignored()</script></head>
          <body>
            <h1>Interface List&lt;E&gt;</h1>
            <p>An ordered collection, also known as a sequence.</p>
          </body>
        </html>
        """,
        encoding="utf-8",
    )

    documents = load_documents(tmp_path / "docs", "jdk8")

    assert len(documents) == 1
    assert documents[0].title == "List (Java Platform SE 8)"
    assert "An ordered collection" in documents[0].text
    assert "ignored()" not in documents[0].text
    assert documents[0].source_path.endswith("api/java/util/List.html")


def test_load_documents_extracts_supported_files_from_jar(tmp_path: Path):
    docs_dir = tmp_path / "docs" / "jdk8"
    docs_dir.mkdir(parents=True)
    jar_path = docs_dir / "jdk8-docs.jar"
    with ZipFile(jar_path, "w") as archive:
        archive.writestr(
            "api/java/util/Map.html",
            """
            <html>
              <head><title>Map (Java Platform SE 8)</title><script>ignored()</script></head>
              <body>
                <h1>Interface Map&lt;K,V&gt;</h1>
                <p>An object that maps keys to values.</p>
              </body>
            </html>
            """,
        )
        archive.writestr("api/java/util/Map.class", "not documentation")
        archive.writestr("resources/logo.png", b"not documentation")

    documents = load_documents(tmp_path / "docs", "jdk8")

    assert len(documents) == 1
    assert documents[0].title == "Map (Java Platform SE 8)"
    assert "An object that maps keys to values" in documents[0].text
    assert "ignored()" not in documents[0].text
    assert documents[0].source_path == "jdk8-docs.jar!/api/java/util/Map.html"


def test_load_documents_combines_expanded_files_and_jar_files(tmp_path: Path):
    docs_dir = tmp_path / "docs" / "jdk8"
    docs_dir.mkdir(parents=True)
    (docs_dir / "overview.md").write_text(
        "JDK overview documentation contains enough prose to be indexed.",
        encoding="utf-8",
    )
    with ZipFile(docs_dir / "references.jar", "w") as archive:
        archive.writestr(
            "api/java/lang/String.html",
            "<html><head><title>String</title></head><body>Strings are constant values in Java programs.</body></html>",
        )

    documents = load_documents(tmp_path / "docs", "jdk8")

    assert [document.source_path for document in documents] == [
        "overview.md",
        "references.jar!/api/java/lang/String.html",
    ]


def test_chunk_document_preserves_metadata_and_overlap():
    chunks = chunk_document(
        text="alpha beta gamma delta epsilon zeta eta theta iota kappa lambda",
        version="jdk8",
        source_path="api/example.html",
        title="Example",
        chunk_size=35,
        overlap=10,
    )

    assert len(chunks) > 1
    assert chunks[0].metadata["version"] == "jdk8"
    assert chunks[0].metadata["source_path"] == "api/example.html"
    assert chunks[0].metadata["title"] == "Example"
    assert chunks[0].metadata["chunk_index"] == 0
    assert chunks[1].metadata["chunk_index"] == 1
    assert chunks[0].text != chunks[1].text
