from backend.app.models import RetrievedChunk


def build_rag_messages(version: str, query: str, chunks: list[RetrievedChunk]) -> list[dict[str, str]]:
    """Build the Ollama chat messages for a retrieval-augmented answer."""
    context = "\n\n".join(_format_chunk(index, chunk) for index, chunk in enumerate(chunks, start=1))
    # Keep the behavioral rules in the user message so the model sees them next
    # to the retrieved context and the user's actual question.
    user_prompt = f"""Target Java version: {version}

Use only the provided documentation context to answer the question.

Rules:
- Return a practical step-by-step guide.
- Include concise Java examples when useful.
- Do not invent APIs from newer Java versions.
- If the documentation context is not enough, say what is missing.
- Cite the source filenames used.

Documentation context:
{context or "No relevant documentation context was found."}

User question:
{query}
"""
    return [
        {
            "role": "system",
            "content": "You are a careful Java documentation assistant for local JDK documentation.",
        },
        {"role": "user", "content": user_prompt},
    ]


def _format_chunk(index: int, chunk: RetrievedChunk) -> str:
    """Format one retrieved chunk as numbered prompt context."""
    return (
        f"[{index}] path: {chunk.path}\n"
        f"title: {chunk.title}\n"
        f"content: {chunk.text}"
    )
