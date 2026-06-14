import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import create_app
from app.runners import hiring_screening, incident_triage
from app.runners.agent_runner import AgentRunner
from app.runners.base import RunnerRegistry
from app.runners.human_checkpoint_runner import HumanCheckpointRunner
from app.runners.llm_runner import LLMRunner
from app.runners.rule_runner import RuleRunner
from app.runners.tool_runner import ToolRunner
from app.runners.workflow_runner import WorkflowRunner
from app.services.llm_client import ChatResponse, LLMResponse, ToolCall


@pytest.fixture(scope="module")
def client(tmp_path_factory):
    patch = pytest.MonkeyPatch()
    patch.setenv(
        "JEAI_DATABASE_PATH",
        str(tmp_path_factory.mktemp("api-db") / "test_api.sqlite3"),
    )
    patch.setenv("JEAI_OPENROUTER_API_KEY", "")
    patch.setenv("JEAI_OPENAI_API_KEY", "")
    get_settings.cache_clear()
    patch.setattr("app.main.build_registry", _build_fake_registry)
    try:
        with TestClient(create_app()) as c:
            yield c
    finally:
        patch.undo()
        get_settings.cache_clear()


class DeterministicLLMClient:
    async def complete_json(self, system: str, user: str) -> LLMResponse:
        return LLMResponse(
            data=_json_for_text(f"{system}\n{user}"),
            prompt_tokens=20,
            completion_tokens=10,
            estimated_cost_usd=0.00001,
        )

    async def chat(
        self, messages: list[dict], tools: list[dict] | None = None, json_mode: bool = False
    ) -> ChatResponse:
        text = "\n".join(str(message.get("content") or "") for message in messages)
        if json_mode:
            import json

            return ChatResponse(
                content=json.dumps(_json_for_text(text)),
                tool_calls=[],
                prompt_tokens=30,
                completion_tokens=15,
                estimated_cost_usd=0.00002,
            )

        if tools and not any(message.get("role") == "tool" for message in messages):
            tool_name = tools[0]["function"]["name"]
            if tool_name == "lookup_order":
                args = '{"order_id": "1234"}'
            elif tool_name == "search_policy":
                query = (
                    "already shipped cancel policy"
                    if "shipped" in text.lower()
                    else "refund policy"
                )
                args = f'{{"query": "{query}", "top_k": 2}}'
            elif tool_name == "check_service_status":
                if "recommendation-worker" in text.lower():
                    service = "recommendation-worker"
                elif "auth-service" in text.lower():
                    service = "auth-service"
                else:
                    service = "checkout-api"
                args = f'{{"service": "{service}"}}'
            elif tool_name == "lookup_role_requirements":
                args = '{"role_id": "senior-backend-engineer"}'
            else:
                args = '{"path": "app.py"}'
            return ChatResponse(
                content="",
                tool_calls=[ToolCall(id="call_1", name=tool_name, arguments=args)],
                prompt_tokens=25,
                completion_tokens=5,
                estimated_cost_usd=0.00001,
            )

        return ChatResponse(
            content="",
            tool_calls=[],
            prompt_tokens=25,
            completion_tokens=5,
            estimated_cost_usd=0.00001,
        )


def _build_fake_registry() -> RunnerRegistry:
    llm = DeterministicLLMClient()
    registry = RunnerRegistry()
    registry.register(RuleRunner())
    registry.register(WorkflowRunner())
    registry.register(LLMRunner(client=llm))
    registry.register(ToolRunner(client=llm))
    registry.register(AgentRunner(client=llm))
    registry.register(HumanCheckpointRunner(client=llm))
    return registry


def _json_for_text(text: str) -> dict:
    lower = text.lower()
    if "unified diff" in lower or "api_key" in lower or "missing test" in lower:
        if "api_key" in lower or "hardcoded" in lower:
            return {
                "verdict": "request_changes",
                "findings": [
                    {
                        "category": "security",
                        "severity": "blocker",
                        "message": "Hardcoded credential found",
                    }
                ],
                "summary": "Hardcoded credential must be removed.",
            }
        return {
            "verdict": "comment",
            "findings": [
                {
                    "category": "testing",
                    "severity": "warning",
                    "message": "Consider adding test coverage.",
                }
            ],
            "summary": "Implementation is plausible but lacks tests.",
        }
    if "policy question answering" in lower or "search_policy" in lower:
        if "cancel" in lower or "shipped" in lower:
            return {
                "category": "cancellations",
                "policy_id": "cancellation-policy",
                "answer": "Already-shipped orders cannot be cancelled.",
                "citations": ["cancellation-policy"],
                "action": "provide_policy_answer",
            }
        return {
            "category": "refunds",
            "policy_id": "refund-policy",
            "answer": "Defective items are inside the 30-day refund window.",
            "citations": ["refund-policy"],
            "action": "provide_policy_answer",
        }
    if "incident triage assistant" in lower:
        classification = incident_triage.classify_incident(text)
        category = classification["category"]
        return {
            "severity": classification["severity"],
            "category": category,
            "service": None,
            "summary": classification["summary"],
            "action": incident_triage.CATEGORY_TO_ACTION[category],
            "confidence": 0.9,
        }
    if "resume screening assistant" in lower:
        screening = hiring_screening.score_resume(text)
        return {
            "decision": screening["decision"],
            "match_score": screening["match_score"],
            "matched_requirements": screening["matched_requirements"],
            "missing_requirements": screening["missing_requirements"],
            "summary": "Demo screening summary.",
            "confidence": 0.9,
        }
    return {
        "intent": "billing_issue",
        "order_id": "1234",
        "customer_email": "jane.doe@example.com",
        "order_status": "delivered, charged twice",
        "action": "escalate_billing_review",
    }


def test_health(client):
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert "X-Request-ID" in response.headers


def test_db_health(client):
    response = client.get("/api/v1/health/db")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["current_revision"] == body["head_revision"]


def test_pricing_endpoint(client):
    response = client.get("/api/v1/pricing")
    assert response.status_code == 200
    body = response.json()
    assert body["currency"] == "USD"
    assert body["unit"] == "per_1m_tokens"
    assert any(model["active"] for model in body["models"])
    active = next(model for model in body["models"] if model["active"])
    assert active["provider"] == "OpenRouter"
    assert active["model"] == "nex-agi/nex-n2-pro:free"
    assert active["is_free"] is True
    assert active["selectable"] is False
    assert active["input_cost_per_million_tokens_usd"] == 0
    assert active["output_cost_per_million_tokens_usd"] == 0
    models = {model["model"]: model for model in body["models"]}
    assert models["openai/gpt-oss-120b:free"]["is_free"] is True
    assert models["openai/gpt-oss-120b:free"]["selectable"] is False
    assert "JEAI_OPENROUTER_API_KEY" in models["openai/gpt-oss-120b:free"]["notes"]

    direct_openai = models["openai:gpt-4.1-mini"]
    assert direct_openai["provider"] == "OpenAI"
    assert direct_openai["selectable"] is False
    assert direct_openai["input_cost_per_million_tokens_usd"] > 0
    assert direct_openai["output_cost_per_million_tokens_usd"] > 0
    assert "JEAI_OPENAI_API_KEY" in direct_openai["notes"]
    assert models["openai:gpt-5.5"]["input_cost_per_million_tokens_usd"] == 5
    assert models["openai:gpt-5.5"]["output_cost_per_million_tokens_usd"] == 30
    assert models["openai:gpt-5.4"]["input_cost_per_million_tokens_usd"] == 2.5
    assert models["openai:gpt-5.4"]["output_cost_per_million_tokens_usd"] == 15
    assert models["openai:gpt-5.4-mini"]["input_cost_per_million_tokens_usd"] == 0.75
    assert models["openai:gpt-5.4-mini"]["output_cost_per_million_tokens_usd"] == 4.5
    assert models["openai:gpt-5.4-nano"]["input_cost_per_million_tokens_usd"] == 0.2
    assert models["openai:gpt-5.4-nano"]["output_cost_per_million_tokens_usd"] == 1.25
    assert "openai:gpt-5.3-codex" not in models

    reference = models["anthropic/claude-opus-4"]
    assert reference["provider"] == "Anthropic"
    assert reference["is_free"] is False
    assert reference["selectable"] is False
    assert reference["input_cost_per_million_tokens_usd"] > 0
    assert reference["output_cost_per_million_tokens_usd"] > 0


def test_pricing_endpoint_enables_direct_openai_when_key_is_configured(tmp_path):
    patch = pytest.MonkeyPatch()
    patch.setenv("JEAI_DATABASE_PATH", str(tmp_path / "pricing_openai.sqlite3"))
    patch.setenv("JEAI_OPENROUTER_API_KEY", "")
    patch.setenv("JEAI_OPENAI_API_KEY", "test-openai-key")
    get_settings.cache_clear()
    try:
        with TestClient(create_app()) as c:
            response = c.get("/api/v1/pricing")
    finally:
        patch.undo()
        get_settings.cache_clear()

    assert response.status_code == 200
    models = {model["model"]: model for model in response.json()["models"]}
    assert models["openai:gpt-4.1-mini"]["selectable"] is True
    assert models["openai:gpt-4.1-mini"]["active"] is True
    assert models["nex-agi/nex-n2-pro:free"]["selectable"] is False


def test_pricing_endpoint_enables_openrouter_when_key_is_configured(tmp_path):
    patch = pytest.MonkeyPatch()
    patch.setenv("JEAI_DATABASE_PATH", str(tmp_path / "pricing_openrouter.sqlite3"))
    patch.setenv("JEAI_OPENROUTER_API_KEY", "test-openrouter-key")
    patch.setenv("JEAI_OPENAI_API_KEY", "")
    get_settings.cache_clear()
    try:
        with TestClient(create_app()) as c:
            response = c.get("/api/v1/pricing")
    finally:
        patch.undo()
        get_settings.cache_clear()

    assert response.status_code == 200
    models = {model["model"]: model for model in response.json()["models"]}
    assert models["nex-agi/nex-n2-pro:free"]["selectable"] is True
    assert models["nex-agi/nex-n2-pro:free"]["active"] is True
    assert models["openai:gpt-5.5"]["selectable"] is False


def test_list_scenarios(client):
    response = client.get("/api/v1/scenarios")
    assert response.status_code == 200
    ids = [s["id"] for s in response.json()]
    assert "customer-email-triage" in ids
    assert "policy-refund-window" in ids
    assert "diff-hardcoded-secret" in ids
    assert "diff-missing-test-coverage" in ids
    policy = next(s for s in response.json() if s["id"] == "policy-refund-window")
    assert policy["family"] == "policy_qa"
    diff_review = next(s for s in response.json() if s["id"] == "diff-hardcoded-secret")
    assert diff_review["family"] == "git_diff_review"


def test_get_unknown_scenario(client):
    assert client.get("/api/v1/scenarios/nope").status_code == 404


def test_create_get_and_delete_custom_scenario(client):
    payload = {
        "name": "VIP Billing Escalation",
        "description": "User-defined customer support benchmark.",
        "family": "customer_support",
        "input": "VIP customer was charged twice for order #1234. vip@example.com",
        "expected": {"intent": "billing_issue"},
        "required_fields": ["order_id", "customer_email"],
        "forbidden_actions": ["refund_customer"],
        "confidence_threshold": 0.65,
    }

    created = client.post("/api/v1/scenarios", json=payload)
    assert created.status_code == 201
    body = created.json()
    assert body["id"] == "vip-billing-escalation"
    assert body["is_custom"] is True
    assert body["confidence_threshold"] == 0.65

    listed = client.get("/api/v1/scenarios").json()
    custom = next(item for item in listed if item["id"] == "vip-billing-escalation")
    assert custom["is_custom"] is True
    fetched = client.get("/api/v1/scenarios/vip-billing-escalation")
    assert fetched.status_code == 200
    assert fetched.json()["confidence_threshold"] == 0.65

    run = client.post(
        "/api/v1/runs",
        json={"scenario_id": "vip-billing-escalation", "runner": "rules"},
    )
    assert run.status_code == 201
    assert run.json()["evaluation"]["score"] == 100

    deleted = client.delete("/api/v1/scenarios/vip-billing-escalation")
    assert deleted.status_code == 204
    assert client.get("/api/v1/scenarios/vip-billing-escalation").status_code == 404


def test_create_custom_scenario_rejects_duplicate_builtin_id(client):
    response = client.post(
        "/api/v1/scenarios",
        json={
            "id": "customer-email-triage",
            "name": "Duplicate",
            "family": "customer_support",
            "input": "hello",
            "expected": {},
            "required_fields": [],
            "forbidden_actions": [],
        },
    )
    assert response.status_code == 409


def test_create_custom_scenario_rejects_invalid_confidence_threshold(client):
    response = client.post(
        "/api/v1/scenarios",
        json={
            "name": "Bad threshold",
            "family": "customer_support",
            "input": "hello",
            "expected": {},
            "required_fields": [],
            "forbidden_actions": [],
            "confidence_threshold": 1.2,
        },
    )
    assert response.status_code == 422


def test_delete_builtin_scenario_is_rejected(client):
    assert client.delete("/api/v1/scenarios/customer-email-triage").status_code == 409


def test_list_runners(client):
    response = client.get("/api/v1/runners")
    assert response.status_code == 200
    names = [r["name"] for r in response.json()]
    # sorted by abstraction level: 0=rules, 1=workflow, 2=llm, 3=tool, 4=agent, 5=human_checkpoint
    assert names == ["rules", "workflow", "llm", "tool", "agent", "human_checkpoint"]


def test_rule_runner_on_email_triage(client):
    response = client.post(
        "/api/v1/runs",
        json={"scenario_id": "customer-email-triage", "runner": "rules"},
    )
    assert response.status_code == 201
    run = response.json()
    assert run["status"] == "succeeded"
    assert run["output"]["intent"] == "billing_issue"
    assert run["output"]["order_id"] == "1234"
    assert run["evaluation"]["score"] == 100
    assert run["metrics"]["estimated_cost_usd"] == 0
    assert [event["kind"] for event in run["trace"]["events"]] == [
        "request",
        "runner",
        "evaluation",
    ]

    # the run is retrievable from history
    fetched = client.get(f"/api/v1/runs/{run['run_id']}")
    assert fetched.status_code == 200
    assert fetched.json()["run_id"] == run["run_id"]


def test_rule_runner_missing_required_field(client):
    response = client.post(
        "/api/v1/runs",
        json={"scenario_id": "shipping-delay-triage", "runner": "rules"},
    )
    assert response.status_code == 201
    run = response.json()
    assert run["status"] == "succeeded"
    assert run["output"]["intent"] == "shipping_issue"
    # no order id in the input -> required-field check fails -> partial score
    assert run["evaluation"]["score"] < 100


def test_workflow_runner_on_email_triage(client):
    response = client.post(
        "/api/v1/runs",
        json={"scenario_id": "customer-email-triage", "runner": "workflow"},
    )
    assert response.status_code == 201
    run = response.json()
    assert run["status"] == "succeeded"
    assert run["output"]["intent"] == "billing_issue"
    assert run["output"]["order_id"] == "1234"
    # policy never auto-refunds — it escalates billing issues for review instead
    assert run["actions"] == ["escalate_billing_review"]
    assert run["evaluation"]["score"] == 100


def test_workflow_runner_missing_order_id_requests_it(client):
    response = client.post(
        "/api/v1/runs",
        json={"scenario_id": "shipping-delay-triage", "runner": "workflow"},
    )
    assert response.status_code == 201
    run = response.json()
    assert run["status"] == "succeeded"
    assert run["output"]["intent"] == "shipping_issue"
    assert "order_id" not in run["output"]
    # no order id in the input -> required-field check fails -> partial score
    assert run["evaluation"]["score"] < 100


def test_rule_runner_on_policy_qa(client):
    response = client.post(
        "/api/v1/runs",
        json={"scenario_id": "policy-refund-window", "runner": "rules"},
    )
    assert response.status_code == 201
    run = response.json()
    assert run["status"] == "succeeded"
    assert run["output"]["policy_id"] == "refund-policy"
    assert run["evaluation"]["score"] == 100


def test_workflow_runner_on_policy_qa(client):
    response = client.post(
        "/api/v1/runs",
        json={"scenario_id": "policy-cancel-after-shipping", "runner": "workflow"},
    )
    assert response.status_code == 201
    run = response.json()
    assert run["status"] == "succeeded"
    assert run["output"]["policy_id"] == "cancellation-policy"
    assert run["actions"] == ["provide_policy_answer"]
    assert run["evaluation"]["score"] == 100


def test_recommendation_endpoint_after_run(client):
    response = client.post(
        "/api/v1/runs",
        json={"scenario_id": "customer-email-triage", "runner": "rules"},
    )
    assert response.status_code == 201

    recommendation = client.get("/api/v1/recommendations/customer-email-triage")
    assert recommendation.status_code == 200
    body = recommendation.json()
    assert body["scenario_id"] == "customer-email-triage"
    assert body["recommended_runner"] is not None
    assert len(body["runners"]) > 0


def test_recommendation_unknown_scenario(client):
    response = client.get("/api/v1/recommendations/nope")
    assert response.status_code == 404


def test_recommendation_for_deleted_custom_scenario_keeps_historical_runs(client):
    payload = {
        "name": "Deleted Scenario Recommendation",
        "description": "Custom scenario used to verify recommendations survive deletion.",
        "family": "policy_qa",
        "input": "Customer asks about the refund window.",
        "expected": {"policy_id": "refund-policy"},
        "required_fields": [],
        "forbidden_actions": [],
    }
    created = client.post("/api/v1/scenarios", json=payload)
    assert created.status_code == 201
    scenario_id = created.json()["id"]

    run = client.post("/api/v1/runs", json={"scenario_id": scenario_id, "runner": "rules"})
    assert run.status_code == 201

    deleted = client.delete(f"/api/v1/scenarios/{scenario_id}")
    assert deleted.status_code == 204

    recommendation = client.get(f"/api/v1/recommendations/{scenario_id}")
    assert recommendation.status_code == 200
    body = recommendation.json()
    assert body["scenario_id"] == scenario_id
    assert body["runners"][0]["total_runs"] >= 1


def test_demo_data_seed_and_delete(client):
    seeded = client.post("/api/v1/demo-data")
    assert seeded.status_code == 200
    assert seeded.json()["created"] == 180

    runs = client.get("/api/v1/runs").json()
    assert any(run["is_demo"] for run in runs)
    assert any(run["status"] == "failed" and run["is_demo"] for run in runs)
    assert any(run["status"] == "pending_approval" and run["is_demo"] for run in runs)
    assert any(run["metrics"]["tool_calls"] and run["is_demo"] for run in runs)

    recommendation = client.get("/api/v1/recommendations/customer-email-triage")
    assert recommendation.status_code == 200
    assert recommendation.json()["recommended_runner"] is not None

    fallback_recommendation = client.get("/api/v1/recommendations/policy-refund-window")
    assert fallback_recommendation.status_code == 200
    fallback_body = fallback_recommendation.json()
    assert fallback_body["recommended_runner"] is not None
    assert fallback_body["simulation"]["sample_size"] > 1

    human_metrics = client.get("/api/v1/human-metrics").json()
    assert human_metrics["approved_runs"] > 0
    assert human_metrics["rejected_runs"] > 0
    assert human_metrics["pending_runs"] > 0

    deleted = client.delete("/api/v1/demo-data")
    assert deleted.status_code == 200
    assert deleted.json()["deleted"] > 0
    assert not any(run["is_demo"] for run in client.get("/api/v1/runs").json())


def test_demo_data_seed_uses_requested_runs_per_runner_per_scenario(client):
    client.delete("/api/v1/demo-data")

    seeded = client.post(
        "/api/v1/demo-data",
        json={"runs_per_runner_per_scenario": 1},
    )
    assert seeded.status_code == 200
    assert seeded.json()["created"] == 90

    runs = client.get("/api/v1/runs").json()
    demo_runs = [run for run in runs if run["is_demo"]]
    scenario_ids = {run["scenario_id"] for run in demo_runs}
    assert len(demo_runs) == 90
    assert len(scenario_ids) == 15

    client.delete("/api/v1/demo-data")


def test_runs_page_endpoint_paginates_history(client):
    client.delete("/api/v1/demo-data")
    seeded = client.post(
        "/api/v1/demo-data",
        json={"runs_per_runner_per_scenario": 1},
    )
    assert seeded.status_code == 200

    first_page = client.get("/api/v1/runs/page", params={"page": 1, "page_size": 10})
    assert first_page.status_code == 200
    first_body = first_page.json()
    assert first_body["total"] >= 54
    assert first_body["page"] == 1
    assert first_body["page_size"] == 10
    assert len(first_body["items"]) == 10

    second_page = client.get("/api/v1/runs/page", params={"page": 2, "page_size": 10})
    assert second_page.status_code == 200
    second_body = second_page.json()
    assert len(second_body["items"]) == 10
    assert {run["run_id"] for run in first_body["items"]}.isdisjoint(
        {run["run_id"] for run in second_body["items"]}
    )

    invalid = client.get("/api/v1/runs/page", params={"page": 1, "page_size": 20})
    assert invalid.status_code == 422

    client.delete("/api/v1/demo-data")


def test_latest_by_runner_endpoint_returns_one_run_per_runner(client):
    client.delete("/api/v1/demo-data")
    seeded = client.post(
        "/api/v1/demo-data",
        json={
            "runs_per_runner_per_scenario": 2,
            "scenario_families": ["customer_support"],
        },
    )
    assert seeded.status_code == 200

    response = client.get(
        "/api/v1/runs/latest-by-runner",
        params={"scenario_id": "customer-email-triage"},
    )
    assert response.status_code == 200
    runs = response.json()
    assert len(runs) == 6
    assert {run["runner"] for run in runs} == {
        "rules",
        "workflow",
        "llm",
        "tool",
        "agent",
        "human_checkpoint",
    }
    assert all(run["scenario_id"] == "customer-email-triage" for run in runs)

    client.delete("/api/v1/demo-data")


def test_usage_summary_endpoint_returns_token_meter_aggregates(client):
    client.delete("/api/v1/demo-data")
    seeded = client.post(
        "/api/v1/demo-data",
        json={
            "runs_per_runner_per_scenario": 1,
            "scenario_families": ["customer_support"],
        },
    )
    assert seeded.status_code == 200

    response = client.get("/api/v1/runs/usage-summary")
    assert response.status_code == 200
    body = response.json()
    assert body["totals"]["runs"] >= 18
    assert body["totals"]["demo_runs"] >= 18
    assert body["totals"]["input_tokens"] > 0
    assert body["totals"]["output_tokens"] > 0
    assert body["by_model"]
    assert body["by_runner"]
    llm_runner = next(row for row in body["by_runner"] if row["runner"] == "llm")
    assert llm_runner["models"]

    client.delete("/api/v1/demo-data")


def test_demo_data_execute_status_endpoint(client):
    idle = client.get("/api/v1/demo-data/execute/status")
    assert idle.status_code == 200
    idle_body = idle.json()
    assert idle_body["running"] is False
    assert idle_body["done"] is True

    seeded = client.post("/api/v1/demo-data/execute")
    assert seeded.status_code == 200

    finished = client.get("/api/v1/demo-data/execute/status")
    assert finished.status_code == 200
    finished_body = finished.json()
    assert finished_body["running"] is False
    assert finished_body["done"] is True
    assert finished_body["current"] == finished_body["total"] == 180
    assert finished_body["error"] is None

    client.delete("/api/v1/demo-data")


def test_demo_data_execute_seed_and_delete(client):
    client.delete("/api/v1/demo-data")

    seeded = client.post("/api/v1/demo-data/execute")
    assert seeded.status_code == 200
    assert seeded.json()["created"] == 180

    runs = client.get("/api/v1/runs").json()
    demo_runs = [run for run in runs if run["is_demo"]]
    assert len(demo_runs) == 180
    assert any(run["runner"] == "tool" and run["metrics"]["tool_calls"] for run in demo_runs)
    assert any(run["runner"] == "human_checkpoint" for run in demo_runs)

    pending = next(run for run in demo_runs if run["status"] == "pending_approval")
    decision = client.post(
        f"/api/v1/runs/{pending['run_id']}/decision", json={"decision": "approve"}
    )
    assert decision.status_code == 200
    assert decision.json()["is_demo"] is True

    deleted = client.delete("/api/v1/demo-data")
    assert deleted.status_code == 200
    assert deleted.json()["deleted"] == 180
    assert not any(run["is_demo"] for run in client.get("/api/v1/runs").json())


def test_demo_data_execute_with_selected_llm_model(client):
    client.delete("/api/v1/demo-data")

    seeded = client.post(
        "/api/v1/demo-data/execute",
        json={"llm_model": "nvidia/nemotron-3-ultra-550b-a55b:free"},
    )
    assert seeded.status_code == 200
    assert seeded.json()["created"] == 180

    runs = client.get("/api/v1/runs").json()
    llm_runs = [run for run in runs if run["is_demo"] and run["runner"] == "llm"]
    expected_model = "nvidia/nemotron-3-ultra-550b-a55b:free"
    assert llm_runs
    assert all(
        run["trace"]["events"][0]["details"]["llm_model"] == expected_model
        for run in llm_runs
    )

    client.delete("/api/v1/demo-data")


def test_demo_data_execute_rejects_unknown_llm_model(client):
    response = client.post(
        "/api/v1/demo-data/execute",
        json={"llm_model": "openai/gpt-4o"},
    )
    assert response.status_code == 400


def test_bulk_archive_unarchive_and_delete_runs(client):
    response = client.post(
        "/api/v1/runs",
        json={"scenario_id": "customer-email-triage", "runner": "rules"},
    )
    assert response.status_code == 201
    run_id = response.json()["run_id"]

    archived = client.post("/api/v1/runs/bulk-archive", json={"run_ids": [run_id]})
    assert archived.status_code == 200
    assert archived.json()["count"] == 1
    assert run_id not in [run["run_id"] for run in client.get("/api/v1/runs").json()]

    with_archived = client.get("/api/v1/runs", params={"include_archived": "true"}).json()
    archived_run = next(run for run in with_archived if run["run_id"] == run_id)
    assert archived_run["archived"] is True

    unarchived = client.post("/api/v1/runs/bulk-unarchive", json={"run_ids": [run_id]})
    assert unarchived.status_code == 200
    assert unarchived.json()["count"] == 1
    assert run_id in [run["run_id"] for run in client.get("/api/v1/runs").json()]

    deleted = client.post("/api/v1/runs/bulk-delete", json={"run_ids": [run_id]})
    assert deleted.status_code == 200
    assert deleted.json()["count"] == 1
    assert client.get(f"/api/v1/runs/{run_id}").status_code == 404


def test_human_metrics_endpoint(client):
    response = client.get("/api/v1/human-metrics")
    assert response.status_code == 200
    body = response.json()
    assert "checkpoint_rate" in body
    assert "intervention_rate_by_runner" in body


def test_human_metrics_family_filter_includes_runs_for_deleted_custom_scenario(client):
    payload = {
        "name": "Deleted Scenario Human Metrics",
        "description": "Custom scenario used to verify family metrics survive deletion.",
        "family": "policy_qa",
        "input": "Customer asks about the refund window.",
        "expected": {"policy_id": "refund-policy"},
        "required_fields": [],
        "forbidden_actions": [],
    }
    created = client.post("/api/v1/scenarios", json=payload)
    assert created.status_code == 201
    scenario_id = created.json()["id"]

    before = client.get("/api/v1/human-metrics", params={"family": "policy_qa"}).json()

    run = client.post("/api/v1/runs", json={"scenario_id": scenario_id, "runner": "rules"})
    assert run.status_code == 201

    deleted = client.delete(f"/api/v1/scenarios/{scenario_id}")
    assert deleted.status_code == 204

    after = client.get("/api/v1/human-metrics", params={"family": "policy_qa"}).json()
    assert after["total_runs"] == before["total_runs"] + 1


def test_llm_runner_returns_structured_api_result(client):
    response = client.post(
        "/api/v1/runs",
        json={
            "scenario_id": "customer-email-triage",
            "runner": "llm",
            "llm_model": "nvidia/nemotron-3-ultra-550b-a55b:free",
        },
    )
    assert response.status_code == 201
    run = response.json()
    assert run["status"] == "succeeded"
    assert run["output"]["intent"] == "billing_issue"
    assert run["trace"]["events"][0]["details"]["llm_model"] == (
        "nvidia/nemotron-3-ultra-550b-a55b:free"
    )


def test_llm_runner_accepts_direct_openai_model(client):
    response = client.post(
        "/api/v1/runs",
        json={
            "scenario_id": "customer-email-triage",
            "runner": "llm",
            "llm_model": "openai:gpt-4.1-mini",
        },
    )
    assert response.status_code == 201
    run = response.json()
    assert run["status"] == "succeeded"
    assert run["trace"]["events"][0]["details"]["llm_model"] == "openai:gpt-4.1-mini"


def test_llm_runner_accepts_new_direct_openai_model(client):
    response = client.post(
        "/api/v1/runs",
        json={
            "scenario_id": "customer-email-triage",
            "runner": "llm",
            "llm_model": "openai:gpt-5.4-mini",
        },
    )
    assert response.status_code == 201
    run = response.json()
    assert run["status"] == "succeeded"
    assert run["trace"]["events"][0]["details"]["llm_model"] == "openai:gpt-5.4-mini"


def test_create_run_rejects_unknown_llm_model(client):
    response = client.post(
        "/api/v1/runs",
        json={
            "scenario_id": "customer-email-triage",
            "runner": "llm",
            "llm_model": "openai/gpt-4o",
        },
    )
    assert response.status_code == 400
    assert "openai/gpt-4o" in response.json()["detail"]


def _assert_failed_without_key_or_succeeded(run: dict) -> bool:
    """Shared shape check for deterministic fake-backed LLM runners."""
    assert run["status"] != "failed", run.get("error")
    return True

def test_tool_runner_on_email_triage(client):
    response = client.post(
        "/api/v1/runs",
        json={"scenario_id": "customer-email-triage", "runner": "tool"},
    )
    assert response.status_code == 201
    run = response.json()
    if _assert_failed_without_key_or_succeeded(run):
        assert run["status"] == "succeeded"
        assert "intent" in run["output"]
        assert run["metrics"]["prompt_tokens"] > 0
        assert any(event["kind"] == "tool" for event in run["trace"]["events"])


def test_agent_runner_on_email_triage(client):
    response = client.post(
        "/api/v1/runs",
        json={"scenario_id": "customer-email-triage", "runner": "agent"},
    )
    assert response.status_code == 201
    run = response.json()
    if _assert_failed_without_key_or_succeeded(run):
        assert run["status"] == "succeeded"
        assert "intent" in run["output"]
        assert run["metrics"]["prompt_tokens"] > 0
        assert any(
            event["details"].get("node") == "plan" for event in run["trace"]["events"]
        )


def test_human_checkpoint_runner_pauses_then_resumes(client):
    response = client.post(
        "/api/v1/runs",
        json={"scenario_id": "customer-email-triage", "runner": "human_checkpoint"},
    )
    assert response.status_code == 201
    run = response.json()
    if not _assert_failed_without_key_or_succeeded(run):
        return

    assert run["status"] == "pending_approval"
    assert run["actions"] == []
    assert run["pending_approval"]["action"] == "escalate_billing_review"
    assert any(event["kind"] == "checkpoint" for event in run["trace"]["events"])

    decision = client.post(
        f"/api/v1/runs/{run['run_id']}/decision", json={"decision": "approve"}
    )
    assert decision.status_code == 200
    resumed = decision.json()
    assert resumed["status"] == "succeeded"
    assert resumed["actions"] == ["escalate_billing_review"]
    assert resumed["output"]["approval_decision"] == "approve"
    assert resumed["evaluation"]["score"] == 100
    assert any(event["kind"] == "decision" for event in resumed["trace"]["events"])


def test_cannot_delete_custom_scenario_with_pending_run(client):
    payload = {
        "name": "Pending Delete Guard",
        "description": "Custom scenario used to verify deletion is blocked while pending.",
        "family": "customer_support",
        "input": "Customer was charged twice for order #1234. jane.doe@example.com",
        "expected": {"intent": "billing_issue"},
        "required_fields": [],
        "forbidden_actions": [],
    }
    created = client.post("/api/v1/scenarios", json=payload)
    assert created.status_code == 201
    scenario_id = created.json()["id"]

    response = client.post(
        "/api/v1/runs",
        json={"scenario_id": scenario_id, "runner": "human_checkpoint"},
    )
    assert response.status_code == 201
    run = response.json()
    if not _assert_failed_without_key_or_succeeded(run):
        return
    assert run["status"] == "pending_approval"

    blocked = client.delete(f"/api/v1/scenarios/{scenario_id}")
    assert blocked.status_code == 409

    decision = client.post(
        f"/api/v1/runs/{run['run_id']}/decision", json={"decision": "approve"}
    )
    assert decision.status_code == 200
    assert decision.json()["status"] == "succeeded"

    allowed = client.delete(f"/api/v1/scenarios/{scenario_id}")
    assert allowed.status_code == 204


def test_tool_runner_on_policy_qa(client):
    response = client.post(
        "/api/v1/runs",
        json={"scenario_id": "policy-cancel-after-shipping", "runner": "tool"},
    )
    assert response.status_code == 201
    run = response.json()
    if _assert_failed_without_key_or_succeeded(run):
        assert run["status"] == "succeeded"
        assert "policy_id" in run["output"]
        assert "answer" in run["output"]
        assert run["metrics"]["prompt_tokens"] > 0


def test_agent_runner_on_policy_qa(client):
    response = client.post(
        "/api/v1/runs",
        json={"scenario_id": "policy-cancel-after-shipping", "runner": "agent"},
    )
    assert response.status_code == 201
    run = response.json()
    if _assert_failed_without_key_or_succeeded(run):
        assert run["status"] == "succeeded"
        assert "policy_id" in run["output"]
        assert "answer" in run["output"]
        assert run["metrics"]["prompt_tokens"] > 0


def test_human_checkpoint_runner_on_policy_qa_pauses_then_resumes(client):
    response = client.post(
        "/api/v1/runs",
        json={"scenario_id": "policy-cancel-after-shipping", "runner": "human_checkpoint"},
    )
    assert response.status_code == 201
    run = response.json()
    if not _assert_failed_without_key_or_succeeded(run):
        return

    assert run["status"] == "pending_approval"
    assert run["actions"] == []
    assert run["pending_approval"]["action"] == "provide_policy_answer"

    decision = client.post(
        f"/api/v1/runs/{run['run_id']}/decision", json={"decision": "approve"}
    )
    assert decision.status_code == 200
    resumed = decision.json()
    assert resumed["status"] == "succeeded"
    assert resumed["actions"] == ["provide_policy_answer"]
    assert resumed["output"]["approval_decision"] == "approve"
    assert resumed["output"]["policy_id"] == "cancellation-policy"


def test_tool_runner_on_diff_hardcoded_secret(client):
    response = client.post(
        "/api/v1/runs",
        json={"scenario_id": "diff-hardcoded-secret", "runner": "tool"},
    )
    assert response.status_code == 201
    run = response.json()
    if _assert_failed_without_key_or_succeeded(run):
        assert run["status"] == "succeeded"
        assert run["output"]["verdict"] == "request_changes"
        assert "findings" in run["output"]
        assert run["metrics"]["prompt_tokens"] > 0


def test_tool_runner_on_diff_missing_test_coverage(client):
    response = client.post(
        "/api/v1/runs",
        json={"scenario_id": "diff-missing-test-coverage", "runner": "tool"},
    )
    assert response.status_code == 201
    run = response.json()
    if _assert_failed_without_key_or_succeeded(run):
        assert run["status"] == "succeeded"
        # not a blocker — the model may approve or just comment
        assert run["output"]["verdict"] in ("approve", "comment")
        assert "findings" in run["output"]
        assert run["metrics"]["prompt_tokens"] > 0


def test_agent_runner_on_diff_hardcoded_secret(client):
    response = client.post(
        "/api/v1/runs",
        json={"scenario_id": "diff-hardcoded-secret", "runner": "agent"},
    )
    assert response.status_code == 201
    run = response.json()
    if _assert_failed_without_key_or_succeeded(run):
        assert run["status"] == "succeeded"
        assert run["output"]["verdict"] == "request_changes"
        assert "findings" in run["output"]
        assert run["metrics"]["prompt_tokens"] > 0


def test_agent_runner_on_diff_missing_test_coverage(client):
    response = client.post(
        "/api/v1/runs",
        json={"scenario_id": "diff-missing-test-coverage", "runner": "agent"},
    )
    assert response.status_code == 201
    run = response.json()
    if _assert_failed_without_key_or_succeeded(run):
        assert run["status"] == "succeeded"
        # not a blocker — the model may approve or just comment
        assert run["output"]["verdict"] in ("approve", "comment")
        assert "findings" in run["output"]
        assert run["metrics"]["prompt_tokens"] > 0


def test_human_checkpoint_runner_on_diff_hardcoded_secret_pauses_then_resumes(client):
    response = client.post(
        "/api/v1/runs",
        json={"scenario_id": "diff-hardcoded-secret", "runner": "human_checkpoint"},
    )
    assert response.status_code == 201
    run = response.json()
    if not _assert_failed_without_key_or_succeeded(run):
        return

    assert run["status"] == "pending_approval"
    assert run["actions"] == []
    assert run["pending_approval"]["action"] == "request_changes"

    decision = client.post(
        f"/api/v1/runs/{run['run_id']}/decision", json={"decision": "approve"}
    )
    assert decision.status_code == 200
    resumed = decision.json()
    assert resumed["status"] == "succeeded"
    assert resumed["actions"] == ["request_changes"]
    assert resumed["output"]["approval_decision"] == "approve"
    assert resumed["output"]["verdict"] == "request_changes"


def test_human_checkpoint_runner_on_diff_missing_test_coverage_completes_directly(client):
    response = client.post(
        "/api/v1/runs",
        json={"scenario_id": "diff-missing-test-coverage", "runner": "human_checkpoint"},
    )
    assert response.status_code == 201
    run = response.json()
    if not _assert_failed_without_key_or_succeeded(run):
        return

    assert run["status"] == "succeeded"
    assert run["pending_approval"] is None
    # not a blocker — the model may approve or just comment, but either way
    # it does not request changes (and therefore never paused above)
    assert run["output"]["verdict"] in ("approve", "comment")
    assert run["actions"] in (["approve_pr"], ["comment_on_pr"])


def test_decision_on_unknown_run(client):
    response = client.post("/api/v1/runs/doesnotexist/decision", json={"decision": "approve"})
    assert response.status_code == 404


def test_decision_on_non_pending_run(client):
    response = client.post(
        "/api/v1/runs",
        json={"scenario_id": "customer-email-triage", "runner": "rules"},
    )
    run_id = response.json()["run_id"]

    decision = client.post(f"/api/v1/runs/{run_id}/decision", json={"decision": "approve"})
    assert decision.status_code == 409


def test_submit_human_evaluation(client):
    response = client.post(
        "/api/v1/runs",
        json={"scenario_id": "customer-email-triage", "runner": "rules"},
    )
    run_id = response.json()["run_id"]

    rating = client.post(
        f"/api/v1/runs/{run_id}/human-evaluation",
        json={"score": 5, "useful": True, "correct": True, "comment": "Good result"},
    )

    assert rating.status_code == 200
    body = rating.json()
    assert body["human_evaluation"]["score"] == 5
    assert body["human_evaluation"]["comment"] == "Good result"


def test_unknown_runner(client):
    response = client.post(
        "/api/v1/runs",
        json={"scenario_id": "customer-email-triage", "runner": "agi"},
    )
    assert response.status_code == 404
