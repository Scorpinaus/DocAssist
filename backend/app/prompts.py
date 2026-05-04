from backend.app.models import AnswerWorkspace, EvidenceItem, RetrievedChunk
from backend.app.task_workspace import build_answer_workspace


def build_rag_messages(version: str, query: str, chunks: list[RetrievedChunk]) -> list[dict[str, str]]:
    """Build the Ollama chat messages for a retrieval-augmented answer."""
    workspace = build_answer_workspace(version, query, chunks)
    return build_workspace_messages(workspace)


def build_workspace_messages(workspace: AnswerWorkspace) -> list[dict[str, str]]:
    """Build the Ollama chat messages from a structured answer workspace."""
    task = workspace.task
    steps = "\n".join(f"- {step}" for step in task.steps)
    evidence = "\n\n".join(_format_evidence_item(item) for item in task.evidence)
    gaps = "\n".join(f"- {gap}" for gap in task.gaps)
    # Keep the behavioral rules in the user message so the model sees them next
    # to the task workspace and the user's actual question.
    user_prompt = f"""Target Java version: {task.version}

Use only the provided documentation context to answer the question.

Rules:
- Return a practical step-by-step guide.
- Include concise Java examples when useful.
- Do not invent APIs from newer Java versions.
- If the documentation context is not enough, say what is missing.
- Cite the source filenames used.

Temporary task workspace:
Intent:
{task.intent}

Task plan:
{steps}

Evidence board:
{evidence or "No relevant documentation evidence was retrieved."}

Known gaps:
{gaps or "- None identified from retrieval."}

User question:
{task.query}
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


def _format_evidence_item(item: EvidenceItem) -> str:
    """Format one evidence board item for answer synthesis."""
    return (
        f"[{item.id}] path: {item.path}\n"
        f"title: {item.title}\n"
        f"score: {item.score if item.score is not None else 'unknown'}\n"
        f"relevance: {item.relevanceNote}\n"
        f"snippet: {item.snippet}"
    )
