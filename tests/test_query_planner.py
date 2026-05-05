from backend.app.query_planner import build_query_plan


def test_query_planner_builds_stable_retrieval_steps():
    plan, mode = build_query_plan("How do I run code in a thread?")

    assert mode == "deterministic"
    assert [step.id for step in plan] == ["S1", "S2", "S3"]
    assert [step.title for step in plan] == [
        "Identify the documentation topic",
        "Gather API details",
        "Check usage constraints and examples",
    ]
    assert [step.retrievalQuery for step in plan] == [
        "How do I run code in a thread?",
        "How do I run code in a thread? API classes methods behavior",
        "How do I run code in a thread? examples constraints exceptions",
    ]
    assert all(step.status == "pending" for step in plan)


class FakePlannerClient:
    def __init__(self, response: str):
        self.response = response
        self.messages = None

    def chat(self, messages):
        self.messages = messages
        return self.response


def test_query_planner_uses_model_json_when_enabled():
    client = FakePlannerClient(
        """
        {
          "steps": [
            {
              "title": "Find Runnable docs",
              "description": "Locate the Runnable interface contract.",
              "retrievalQuery": "Runnable interface run method"
            },
            {
              "title": "Find Thread docs",
              "description": "Locate Thread construction and start behavior.",
              "retrievalQuery": "Thread constructor start Runnable"
            }
          ]
        }
        """
    )

    plan, mode = build_query_plan(
        "How do I run code in a thread?",
        planner_mode="model",
        planner_client=client,
        max_steps=5,
    )

    assert mode == "model"
    assert [step.id for step in plan] == ["S1", "S2"]
    assert [step.title for step in plan] == ["Find Runnable docs", "Find Thread docs"]
    assert [step.retrievalQuery for step in plan] == [
        "Runnable interface run method",
        "Thread constructor start Runnable",
    ]
    assert "Return only valid JSON" in client.messages[-1]["content"]


def test_query_planner_falls_back_when_model_json_is_invalid():
    plan, mode = build_query_plan(
        "How do I run code in a thread?",
        planner_mode="model",
        planner_client=FakePlannerClient("not json"),
    )

    assert mode == "fallback"
    assert [step.id for step in plan] == ["S1", "S2", "S3"]
    assert plan[0].retrievalQuery == "How do I run code in a thread?"


def test_query_planner_caps_and_normalizes_model_steps():
    client = FakePlannerClient(
        {
            "steps": [
                {"id": "custom", "title": "One", "description": "First", "retrievalQuery": "one"},
                {"id": "custom", "title": "Two", "description": "Second", "retrievalQuery": "two"},
                {"id": "custom", "title": "Three", "description": "Third", "retrievalQuery": "three"},
            ]
        }
    )

    plan, mode = build_query_plan("Question?", planner_mode="model", planner_client=client, max_steps=2)

    assert mode == "model"
    assert [step.id for step in plan] == ["S1", "S2"]
    assert [step.retrievalQuery for step in plan] == ["one", "two"]
