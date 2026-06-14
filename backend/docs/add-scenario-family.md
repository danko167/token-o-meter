# How to Add a New Scenario Family

Use this checklist when introducing a new task domain such as contract review,
incident triage, invoice processing, or sales lead qualification.

## 1. Define Scenarios

Add one or more YAML files under `scenarios/`:

```yaml
id: invoice-payment-dispute
name: Invoice Payment Dispute
description: Classify an invoice dispute and choose the next action.
family: invoice_ops
input: |
  Customer message or domain input goes here.
expected:
  intent: payment_dispute
  action: escalate_finance_review
required_fields:
  - intent
forbidden_actions:
  - issue_refund
```

Keep expected outputs focused on fields the evaluator can verify reliably.

## 2. Add Domain Logic

Create a family module in `app/runners/`, for example
`app/runners/invoice_ops.py`. Put shared constants, prompts, output parsers, and
fallback proposals there.

Typical contents:

- allowed labels/actions
- system prompt
- final JSON prompt
- parser that normalizes model output
- deterministic fallback proposal

## 3. Teach Each Runner

Update the runner implementations only where the new family needs special
behavior:

- `rule_runner.py`: add deterministic patterns and decision rules.
- `workflow_runner.py`: add explicit workflow steps for the family.
- `llm_runner.py`: route to the family prompt/parser.
- `tool_runner.py`: add a family-specific tool if needed.
- `agent_runner.py`: register a family graph module.
- `human_checkpoint_runner.py`: register the same graph module — no
  family-specific logic needed.

For LangGraph families, create a graph module following the existing
`policy_agent_graph.py` or `diff_agent_graph.py` pattern. Reuse the shared trace
helpers from `agent_graph.py` so node events stay consistent. Define a
`RISKY_ACTIONS: set[str]` constant for actions with real-world consequences,
and have your `decide()` step's JSON contract include a `"confidence"` field
(0.0-1.0). `HumanCheckpointRunner` (Level 5) pauses for human approval via the
shared `app/services/checkpoint_policy.evaluate()`, which checks the proposed
action against `RISKY_ACTIONS`, the scenario's `required_fields`, the
self-reported `confidence` against `confidence_threshold`, and whether the
model needed retries — no per-family approval logic required.

## 4. Add Tools or Corpora

If the family needs retrieval or lookup, add a small service under
`app/services/` and expose a JSON tool schema. Keep demo data deterministic so
tests and demo runs are repeatable.

Examples:

- `policy_docs.py` exposes `search_policy`.
- `repo_files.py` exposes `read_file`.
- `order_lookup.py` exposes `lookup_order`.

## 5. Extend Evaluation

Update `app/services/evaluation.py` so successful runs get meaningful checks.
Prefer deterministic checks first. Add LLM-as-judge only for subjective quality
that cannot be captured with simple expected fields.

## 6. Update Demo Data and Recommendations

Add representative demo runs in `app/services/demo_data.py` so dashboards,
recommendations, traces, and human metrics are populated immediately.

No recommendation-engine changes should be needed unless the family requires a
new reliability threshold or cost model.

## 7. Update Frontend Labels

Add the family to `frontend/src/api/types.ts` and
`frontend/src/lib/scenarioFamilies.ts`. The existing family filters, compare
flow, recommendations, history, and human metrics pages will pick it up.

## 8. Test

Add or update tests for:

- scenario loading
- every runner path that supports the family
- tool behavior
- evaluation checks
- API run creation
- recommendation behavior when demo or historical runs exist

Run:

```powershell
.\.venv\Scripts\python -m ruff check .
.\.venv\Scripts\python -m pytest
cd ..\frontend
npm run lint
npm run build
```
