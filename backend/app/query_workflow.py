from dataclasses import dataclass

from backend.app.models import AnswerWorkspace, QueryStep, RetrievedChunk, Source
from backend.app.prompts import build_workspace_messages
from backend.app.query_planner import build_query_plan
from backend.app.task_workspace import build_evidence_items, build_workspace_from_steps


@dataclass(frozen=True)
class StepRun:
    """Completed retrieval result for one query step."""

    step: QueryStep
    chunks: list[RetrievedChunk]


@dataclass(frozen=True)
class QueryPlan:
    """Planned query steps plus the planner mode used."""

    steps: list[QueryStep]
    planner_mode: str


@dataclass(frozen=True)
class QueryWorkflowResult:
    """Final answer and structured workspace for one user query."""

    answer: str
    sources: list[Source]
    workspace: object
    step_runs: list[StepRun]
    planner_mode: str


@dataclass(frozen=True)
class QuerySynthesis:
    """Prepared prompt material for final answer generation."""

    sources: list[Source]
    workspace: AnswerWorkspace
    messages: list[dict[str, str]]


def plan_query(settings, version: str, query: str, planner_client=None) -> QueryPlan:
    """Return the visible multi-step plan used by the query workflow."""
    steps, planner_mode = build_query_plan(
        query,
        version=version,
        planner_mode=getattr(settings, "query_planner", "deterministic"),
        planner_client=planner_client,
    )
    return QueryPlan(steps=steps, planner_mode=planner_mode)


def run_step(retriever, version: str, step: QueryStep, top_k: int) -> StepRun:
    """Retrieve evidence for one planned step and return an updated step."""
    chunks = retriever.retrieve(version, step.retrievalQuery, top_k)
    evidence = build_evidence_items(chunks)
    status = "completed" if evidence else "blocked"
    gaps = [] if evidence else ["No relevant documentation evidence was retrieved for this step."]
    completed_step = step.model_copy(
        update={
            "status": status,
            "evidence": evidence,
            "result": _step_result(status, len(evidence)),
            "gaps": gaps,
        }
    )
    return StepRun(step=completed_step, chunks=chunks)


def finish_query(
    version: str,
    query: str,
    step_runs: list[StepRun],
    chat_client,
    planner_mode: str = "deterministic",
) -> QueryWorkflowResult:
    """Synthesize the final answer from completed step runs."""
    synthesis = prepare_synthesis(version, query, step_runs, planner_mode=planner_mode)
    answer = chat_client.chat(synthesis.messages)
    return QueryWorkflowResult(
        answer=answer,
        sources=synthesis.sources,
        workspace=synthesis.workspace,
        step_runs=step_runs,
        planner_mode=planner_mode,
    )


def prepare_synthesis(
    version: str,
    query: str,
    step_runs: list[StepRun],
    planner_mode: str = "deterministic",
) -> QuerySynthesis:
    """Prepare workspace, sources, and prompt messages before final generation."""
    steps = [run.step for run in step_runs]
    workspace = build_workspace_from_steps(version, query, steps, planner_mode=planner_mode)
    messages = build_workspace_messages(workspace)
    sources = [
        Source(title=chunk.title, path=chunk.path, snippet=chunk.text[:500], score=chunk.score)
        for chunk in _deduplicate_chunks(chunk for run in step_runs for chunk in run.chunks)
    ]
    return QuerySynthesis(sources=sources, workspace=workspace, messages=messages)


def answer_query(settings, version: str, query: str, retriever, chat_client) -> QueryWorkflowResult:
    """Run the full deterministic multi-step query workflow."""
    plan = plan_query(settings, version, query, chat_client)
    step_runs = [run_step(retriever, version, step, settings.top_k_results) for step in plan.steps]
    return finish_query(version, query, step_runs, chat_client, planner_mode=plan.planner_mode)


def _step_result(status: str, evidence_count: int) -> str:
    if status == "completed":
        return f"Retrieved {evidence_count} evidence item{'' if evidence_count == 1 else 's'} for this step."
    return "No supporting evidence was retrieved for this step."


def _deduplicate_chunks(chunks) -> list[RetrievedChunk]:
    deduplicated = []
    seen = set()
    for chunk in chunks:
        key = (chunk.path, chunk.text[:500])
        if key in seen:
            continue
        seen.add(key)
        deduplicated.append(chunk)
    return deduplicated
