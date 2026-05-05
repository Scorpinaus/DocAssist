from backend.app.models import RetrievedChunk
from backend.app.task_workspace import build_answer_workspace


def test_workspace_builds_multi_step_evidence_board():
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
    assert task.plannerMode == "deterministic"
    assert [step.id for step in task.steps] == ["S1", "S2", "S3"]
    assert task.steps[0].title == "Identify the documentation topic"
    assert task.steps[0].retrievalQuery == "How do I run code in a thread?"
    assert task.steps[0].status == "completed"
    assert task.steps[0].evidence[0].id == "E1"
    assert task.gaps == []
    assert task.evidence[0].id == "E1"
    assert task.evidence[0].path == "api/java/lang/Runnable.html"
    assert "similarity score 0.91" in task.evidence[0].relevanceNote


def test_workspace_records_gap_when_no_evidence_is_retrieved():
    workspace = build_answer_workspace(version="jdk8", query="What is missing?", chunks=[])

    assert workspace.task.evidence == []
    assert workspace.task.gaps == ["No relevant documentation evidence was retrieved for this question."]
    assert workspace.task.plannerMode == "deterministic"
    assert workspace.task.steps[0].status == "blocked"
    assert workspace.task.steps[0].gaps == ["No relevant documentation evidence was retrieved for this step."]
