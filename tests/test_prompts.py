from backend.app.models import RetrievedChunk
from backend.app.prompts import build_rag_messages


def test_prompt_requires_version_scoped_step_by_step_answer():
    messages = build_rag_messages(
        version="jdk8",
        query="How do I create an annotation?",
        chunks=[
            RetrievedChunk(
                text="Annotations are metadata about a program.",
                title="Annotations",
                path="technotes/guides/language/annotations.html",
                score=0.8,
            )
        ],
    )

    combined = "\n".join(message["content"] for message in messages)

    assert "Target Java version: jdk8" in combined
    assert "step-by-step guide" in combined
    assert "Do not invent APIs from newer Java versions" in combined
    assert "technotes/guides/language/annotations.html" in combined
