from backend.app.models import DocumentChunk


def chunk_document(
    text: str,
    version: str,
    source_path: str,
    title: str,
    chunk_size: int = 1200,
    overlap: int = 200,
) -> list[DocumentChunk]:
    """Split one document into overlapping chunks ready for vector indexing.

    Args:
        text: Raw document text extracted by the loader.
        version: Documentation version folder, such as ``jdk8``.
        source_path: Path to the source file relative to the version directory.
        title: Human-readable document title.
        chunk_size: Target maximum number of characters per chunk.
        overlap: Number of characters to repeat between neighboring chunks.

    Returns:
        A list of chunks with metadata needed for retrieval and citation.
    """
    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")
    if overlap < 0 or overlap >= chunk_size:
        raise ValueError("overlap must be non-negative and smaller than chunk_size")

    chunks: list[DocumentChunk] = []
    start = 0
    chunk_index = 0
    # Collapse repeated whitespace so chunk sizes are predictable across HTML,
    # Markdown, and plain text inputs.
    clean_text = " ".join(text.split())

    while start < len(clean_text):
        end = min(start + chunk_size, len(clean_text))
        if end < len(clean_text):
            # Prefer ending at a word boundary when the boundary is not too far
            # from the target size; this keeps snippets readable without making
            # very small chunks.
            boundary = clean_text.rfind(" ", start, end)
            if boundary > start + (chunk_size // 2):
                end = boundary

        chunk_text = clean_text[start:end].strip()
        if chunk_text:
            chunks.append(
                DocumentChunk(
                    text=chunk_text,
                    metadata={
                        "version": version,
                        "source_path": source_path,
                        "title": title,
                        "chunk_index": chunk_index,
                    },
                )
            )
            chunk_index += 1

        if end >= len(clean_text):
            break
        # Step back by the configured overlap so concepts split across a chunk
        # boundary can still be retrieved from either neighboring chunk.
        start = max(0, end - overlap)

    return chunks


def chunk_documents(
    documents,
    version: str,
    chunk_size: int = 1200,
    overlap: int = 200,
) -> list[DocumentChunk]:
    """Chunk a collection of loaded documents for one documentation version."""
    chunks: list[DocumentChunk] = []
    for document in documents:
        chunks.extend(
            chunk_document(
                text=document.text,
                version=version,
                source_path=document.source_path,
                title=document.title,
                chunk_size=chunk_size,
                overlap=overlap,
            )
        )
    return chunks
