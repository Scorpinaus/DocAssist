from pathlib import Path
import re
from zipfile import BadZipFile, ZipFile

from bs4 import BeautifulSoup

from backend.app.models import Document


SUPPORTED_EXTENSIONS = {".html", ".htm", ".txt", ".md"}
SUPPORTED_ARCHIVE_EXTENSIONS = {".jar"}


def available_versions(docs_dir: Path) -> list[str]:
    """Return documentation version folder names found below the docs root."""
    if not docs_dir.exists():
        return []
    return sorted(path.name for path in docs_dir.iterdir() if path.is_dir())


def load_documents(docs_dir: Path, version: str) -> list[Document]:
    """Load supported documentation files for one version into text documents.

    Files that cannot be read, have unsupported extensions, or normalize to very
    short text are skipped. Source paths are stored relative to the version
    directory so citations remain stable if the project root moves.
    """
    version_dir = docs_dir / version
    if not version_dir.exists():
        raise FileNotFoundError(f"Documentation version not found: {version}")

    documents: list[Document] = []
    for path in sorted(version_dir.rglob("*")):
        if not path.is_file():
            continue
        if path.suffix.lower() in SUPPORTED_ARCHIVE_EXTENSIONS:
            documents.extend(_load_archive_documents(path, version_dir))
            continue
        if path.suffix.lower() in SUPPORTED_EXTENSIONS:
            document = _load_document(path, version_dir)
            if document and len(document.text) >= 40:
                documents.append(document)
    return documents


def _load_document(path: Path, version_dir: Path) -> Document | None:
    """Read and normalize a single source file, returning ``None`` when empty."""
    try:
        raw = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return None

    return _document_from_text(
        raw=raw,
        suffix=path.suffix.lower(),
        fallback_title=path.stem,
        source_path=path.relative_to(version_dir).as_posix(),
    )


def _load_archive_documents(path: Path, version_dir: Path) -> list[Document]:
    """Load supported documentation entries from a Java doc archive."""
    documents: list[Document] = []
    archive_source = path.relative_to(version_dir).as_posix()

    try:
        with ZipFile(path) as archive:
            for entry in sorted(archive.infolist(), key=lambda info: info.filename):
                entry_path = Path(entry.filename)
                if entry.is_dir() or entry_path.suffix.lower() not in SUPPORTED_EXTENSIONS:
                    continue
                try:
                    raw = archive.read(entry).decode("utf-8", errors="ignore")
                except OSError:
                    continue
                document = _document_from_text(
                    raw=raw,
                    suffix=entry_path.suffix.lower(),
                    fallback_title=entry_path.stem,
                    source_path=f"{archive_source}!/{entry.filename}",
                )
                if document and len(document.text) >= 40:
                    documents.append(document)
    except BadZipFile as exc:
        raise ValueError(f"Documentation archive is not a valid jar file: {path}") from exc

    return documents


def _document_from_text(raw: str, suffix: str, fallback_title: str, source_path: str) -> Document | None:
    """Normalize one decoded source into a document."""
    if suffix in {".html", ".htm"}:
        title, text = _extract_html(raw)
    else:
        title = fallback_title
        text = raw

    text = normalize_text(text)
    if not text:
        return None

    return Document(
        text=text,
        title=normalize_text(title) or fallback_title,
        source_path=source_path,
    )


def _extract_html(raw: str) -> tuple[str, str]:
    """Extract a title and visible text from an HTML document."""
    soup = BeautifulSoup(raw, "html.parser")
    # Remove page chrome and executable content before collecting text, so the
    # vector index focuses on documentation content users can cite.
    for tag in soup(["script", "style", "noscript", "nav", "footer"]):
        tag.decompose()

    title = ""
    if soup.title and soup.title.string:
        title = soup.title.string
    elif heading := soup.find(["h1", "h2"]):
        title = heading.get_text(" ", strip=True)

    return title, soup.get_text(" ", strip=True)


def normalize_text(text: str) -> str:
    """Collapse whitespace and trim text for consistent downstream chunking."""
    return re.sub(r"\s+", " ", text).strip()
