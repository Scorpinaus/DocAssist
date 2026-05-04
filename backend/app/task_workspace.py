from backend.app.models import AnswerWorkspace, EvidenceItem, RetrievedChunk, RetrievalTaskPlan


def build_answer_workspace(version: str, query: str, chunks: list[RetrievedChunk]) -> AnswerWorkspace:
    """Build a temporary answer workspace from one request and its evidence."""
    evidence = [_build_evidence_item(index, chunk) for index, chunk in enumerate(chunks, start=1)]
    gaps = []
    if not evidence:
        gaps.append("No relevant documentation evidence was retrieved for this question.")

    return AnswerWorkspace(
        task=RetrievalTaskPlan(
            version=version,
            query=query,
            intent=_infer_intent(query),
            steps=[
                "Identify the Java documentation topic requested by the user.",
                "Use the evidence board to extract version-scoped API details.",
                "Synthesize a practical step-by-step answer from supported evidence.",
                "Name missing information when the evidence does not support part of the answer.",
                "Cite the source filenames used in the answer.",
            ],
            evidence=evidence,
            gaps=gaps,
        )
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
