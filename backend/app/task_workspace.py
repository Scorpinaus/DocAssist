from backend.app.models import AnswerWorkspace, EvidenceItem, QueryStep, RetrievedChunk, RetrievalTaskPlan
from backend.app.query_planner import build_query_plan


def build_answer_workspace(
    version: str,
    query: str,
    chunks: list[RetrievedChunk],
    steps: list[QueryStep] | None = None,
    planner_mode: str = "deterministic",
) -> AnswerWorkspace:
    """Build a temporary answer workspace from one request and its evidence."""
    evidence = [_build_evidence_item(index, chunk) for index, chunk in enumerate(chunks, start=1)]
    gaps = []
    if not evidence:
        gaps.append("No relevant documentation evidence was retrieved for this question.")
    planned_steps = steps or build_query_plan(query)[0]
    if steps is None:
        planned_steps = _attach_legacy_step_evidence(planned_steps, evidence)

    return AnswerWorkspace(
        task=RetrievalTaskPlan(
            version=version,
            query=query,
            intent=_infer_intent(query),
            plannerMode=planner_mode,
            steps=planned_steps,
            evidence=evidence,
            gaps=gaps,
        )
    )


def build_workspace_from_steps(
    version: str,
    query: str,
    steps: list[QueryStep],
    planner_mode: str = "deterministic",
) -> AnswerWorkspace:
    """Build a workspace from completed query steps."""
    evidence = _deduplicate_evidence(item for step in steps for item in step.evidence)
    gaps = [gap for step in steps for gap in step.gaps]
    if not evidence:
        gaps.append("No relevant documentation evidence was retrieved for this question.")
    return build_answer_workspace(version, query, [], steps=steps, planner_mode=planner_mode).model_copy(
        update={
            "task": RetrievalTaskPlan(
                version=version,
                query=query,
                intent=_infer_intent(query),
                plannerMode=planner_mode,
                steps=steps,
                evidence=evidence,
                gaps=_deduplicate_strings(gaps),
            )
        }
    )


def _build_evidence_item(index: int, chunk: RetrievedChunk) -> EvidenceItem:
    """Convert a retrieved chunk into a stable evidence board item."""
    return EvidenceItem(
        id=f"E{index}",
        title=chunk.title,
        path=chunk.path,
        snippet=chunk.text[:500],
        score=chunk.score,
        relevanceNote=_build_relevance_note(chunk),
    )


def _infer_intent(query: str) -> str:
    """Describe the user request without adding model-dependent planning."""
    normalized_query = " ".join(query.split())
    return f"Answer the user's Java documentation question: {normalized_query}"


def _build_relevance_note(chunk: RetrievedChunk) -> str:
    """Summarize why a retrieved chunk is on the board."""
    if chunk.score is None:
        return "Retrieved as local documentation evidence for the question."
    return f"Retrieved as local documentation evidence with similarity score {chunk.score:.3g}."


def build_evidence_items(chunks: list[RetrievedChunk]) -> list[EvidenceItem]:
    """Convert retrieved chunks into stable evidence board items."""
    return [_build_evidence_item(index, chunk) for index, chunk in enumerate(chunks, start=1)]


def _attach_legacy_step_evidence(steps: list[QueryStep], evidence: list[EvidenceItem]) -> list[QueryStep]:
    if not steps:
        return steps
    status = "completed" if evidence else "blocked"
    gaps = [] if evidence else ["No relevant documentation evidence was retrieved for this step."]
    steps[0] = steps[0].model_copy(
        update={
            "status": status,
            "evidence": evidence,
            "result": _step_result(status, len(evidence)),
            "gaps": gaps,
        }
    )
    return steps


def _step_result(status: str, evidence_count: int) -> str:
    if status == "completed":
        return f"Retrieved {evidence_count} evidence item{'' if evidence_count == 1 else 's'} for this step."
    return "No supporting evidence was retrieved for this step."


def _deduplicate_evidence(items) -> list[EvidenceItem]:
    deduplicated = []
    seen = set()
    for item in items:
        key = (item.path, item.snippet)
        if key in seen:
            continue
        seen.add(key)
        deduplicated.append(item.model_copy(update={"id": f"E{len(deduplicated) + 1}"}))
    return deduplicated


def _deduplicate_strings(values: list[str]) -> list[str]:
    deduplicated = []
    seen = set()
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        deduplicated.append(value)
    return deduplicated
