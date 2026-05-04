from pathlib import Path
import re

from bs4 import BeautifulSoup

from backend.app.models import Document


SUPPORTED_EXTENSIONS = {".html", ".htm", ".txt", ".md"}


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
        if not path.is_file() or path.suffix.lower() not in SUPPORTED_EXTENSIONS:
            continue
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

    if path.suffix.lower() in {".html", ".htm"}:
        title, text = _extract_html(raw)
    else:
        title = path.stem
        text = raw

    text = normalize_text(text)
    if not text:
        return None

    return Document(
        text=text,
        title=normalize_text(title) or path.stem,
        source_path=path.relative_to(version_dir).as_posix(),
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
