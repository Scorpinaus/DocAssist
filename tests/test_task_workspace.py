from backend.app.models import RetrievedChunk
from backend.app.task_workspace import build_answer_workspace


def test_workspace_builds_stable_evidence_board():
    workspace = build_answer_workspace(
        version="jdk8",
        query="How do I run code in a thread?",
        chunks=[
            RetrievedChunk(
                text="The Runnable interface should be implemented by any class whose instances are intended to be executed by a thread.",
                title="Runnable",
                path="api/java/lang/Runnable.html",
                score=0.91,
            )
        ],
    )

    task = workspace.task

    assert task.version == "jdk8"
    assert task.query == "How do I run code in a thread?"
    assert "Java documentation question" in task.intent
    assert task.steps
    assert task.gaps == []
    assert task.evidence[0].id == "E1"
    assert task.evidence[0].path == "api/java/lang/Runnable.html"
    assert "similarity score 0.91" in task.evidence[0].relevanceNote


def test_workspace_records_gap_when_no_evidence_is_retrieved():
    workspace = build_answer_workspace(version="jdk8", query="What is missing?", chunks=[])

    assert workspace.task.evidence == []
    assert workspace.task.gaps == ["No relevant documentation evidence was retrieved for this question."]
