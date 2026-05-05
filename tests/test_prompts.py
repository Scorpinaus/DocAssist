from backend.app.models import RetrievedChunk
from backend.app.prompts import build_query_plan_messages, build_rag_messages, build_workspace_messages
from backend.app.task_workspace import build_answer_workspace


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


def test_workspace_prompt_includes_task_plan_and_evidence_board():
    workspace = build_answer_workspace(
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

    messages = build_workspace_messages(workspace)
    combined = "\n".join(message["content"] for message in messages)

    assert "Temporary task workspace:" in combined
    assert "Multi-step task plan:" in combined
    assert "[S1] Identify the documentation topic" in combined
    assert "retrieval query: How do I create an annotation?" in combined
    assert "Evidence board:" in combined
    assert "[E1] path: technotes/guides/language/annotations.html" in combined
    assert "Step evidence:" in combined
    assert "Known gaps:" in combined


def test_query_plan_prompt_requests_strict_json():
    messages = build_query_plan_messages("jdk8", "How do I run code in a thread?", max_steps=4)
    combined = "\n".join(message["content"] for message in messages)

    assert "Target Java version: jdk8" in combined
    assert "Return only valid JSON" in combined
    assert '"steps"' in combined
    assert "3 to 4 steps" in combined
