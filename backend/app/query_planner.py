import json

from backend.app.models import QueryStep


def build_query_plan(
    query: str,
    *,
    version: str = "jdk8",
    planner_mode: str = "deterministic",
    planner_client=None,
    max_steps: int = 5,
) -> tuple[list[QueryStep], str]:
    """Build retrieval steps and report which planner produced them."""
    normalized_mode = (planner_mode or "deterministic").strip().lower()
    if normalized_mode == "model" and planner_client is not None:
        try:
            steps = _build_model_query_plan(query, version, planner_client, max_steps)
        except (TypeError, ValueError, json.JSONDecodeError):
            steps = []
        if steps:
            return steps, "model"
        return _build_deterministic_query_plan(query), "fallback"
    return _build_deterministic_query_plan(query), "deterministic"


def _build_deterministic_query_plan(query: str) -> list[QueryStep]:
    """Build deterministic retrieval steps for one user question."""
    normalized_query = " ".join(query.split())
    return [
        QueryStep(
            id="S1",
            title="Identify the documentation topic",
            description="Find the primary Java documentation page or concept that matches the question.",
            retrievalQuery=normalized_query,
        ),
        QueryStep(
            id="S2",
            title="Gather API details",
            description="Retrieve class, method, and behavioral details needed for a version-scoped answer.",
            retrievalQuery=f"{normalized_query} API classes methods behavior",
        ),
        QueryStep(
            id="S3",
            title="Check usage constraints and examples",
            description="Look for examples, constraints, exceptions, and usage notes that affect the final guidance.",
            retrievalQuery=f"{normalized_query} examples constraints exceptions",
        ),
    ]


def _build_model_query_plan(query: str, version: str, planner_client, max_steps: int) -> list[QueryStep]:
    from backend.app.prompts import build_query_plan_messages

    response = planner_client.chat(build_query_plan_messages(version, query, max_steps=max_steps))
    payload = response if isinstance(response, dict) else json.loads(response)
    raw_steps = payload.get("steps")
    if not isinstance(raw_steps, list):
        raise ValueError("Model planner response did not contain a steps list.")

    steps = []
    for raw_step in raw_steps[:max_steps]:
        if not isinstance(raw_step, dict):
            continue
        title = _required_text(raw_step, "title")
        description = _required_text(raw_step, "description")
        retrieval_query = _required_text(raw_step, "retrievalQuery")
        steps.append(
            QueryStep(
                id=f"S{len(steps) + 1}",
                title=title,
                description=description,
                retrievalQuery=retrieval_query,
            )
        )
    return steps


def _required_text(payload: dict, key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str):
        raise ValueError(f"Missing planner field: {key}")
    normalized = " ".join(value.split())
    if not normalized:
        raise ValueError(f"Empty planner field: {key}")
    return normalized
