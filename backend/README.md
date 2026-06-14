# Just enough AI — Backend

FastAPI backend for comparing implementation strategies (rules → LLM → agents) against the same scenarios. See the project brief for the full vision.

## Setup

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
copy .env.example .env
```

## Run

```powershell
uvicorn app.main:app --reload
```

API docs: http://localhost:8000/docs

The default SQLite database is stored at `../data/just_enough_ai.sqlite3`, next to `backend/` and `frontend/`. Keeping it outside `backend/` prevents `uvicorn --reload` from restarting every time run history is written. If you
override `JEAI_DATABASE_PATH`, choose a path outside the watched source tree or add matching `--reload-exclude` flags.

Frontend:

```powershell
cd ..\frontend
npm install
npm run dev
```

Vite prints the local URL, usually http://localhost:5173.

## Test & lint

```powershell
pytest
ruff check .
```

## API surface (v1)

| Method | Path                     | Purpose                              |
|--------|--------------------------|--------------------------------------|
| GET    | /api/v1/health           | Liveness probe                       |
| GET    | /api/v1/scenarios        | List scenarios                       |
| POST   | /api/v1/scenarios        | Create a custom scenario stored in SQLite |
| GET    | /api/v1/scenarios/{id}   | Scenario detail                      |
| DELETE | /api/v1/scenarios/{id}   | Delete a custom scenario             |
| GET    | /api/v1/runners          | List runners (by abstraction level)  |
| GET    | /api/v1/pricing          | Selectable OpenRouter/direct OpenAI model prices, plus reference-only commercial model prices for cost comparison |
| POST   | /api/v1/runs             | Execute a runner against a scenario  |
| GET    | /api/v1/runs             | Run history (newest first); `?include_archived=true` to include archived runs |
| GET    | /api/v1/runs/page        | Paginated run history                |
| GET    | /api/v1/runs/latest-by-runner | Latest run per runner for one scenario |
| GET    | /api/v1/runs/usage-summary | Token and estimated spend summary by model and runner |
| GET    | /api/v1/runs/{run_id}    | Run detail                           |
| POST   | /api/v1/runs/{run_id}/decision | Approve/reject a `pending_approval` run (Level 5) |
| POST   | /api/v1/runs/{run_id}/human-evaluation | Save a manual post-run score/comment |
| POST   | /api/v1/runs/bulk-archive | Archive a batch of runs (hidden from history by default) |
| POST   | /api/v1/runs/bulk-unarchive | Restore a batch of archived runs    |
| POST   | /api/v1/runs/bulk-delete | Permanently delete a batch of runs   |
| GET    | /api/v1/recommendations/{scenario_id} | Recommend the cheapest reliable runner from recorded evidence |
| GET    | /api/v1/human-metrics   | Aggregate checkpoint, approval, rejection, and escalation metrics |
| POST   | /api/v1/demo-data       | Seed representative demo runs for all dashboards (fast, deterministic, no LLM calls); body sets `runs_per_runner_per_scenario` (1-20, default 2) |
| POST   | /api/v1/demo-data/execute | Add demo runs by executing scenarios through the real runners, optionally with a chosen LLM model |
| GET    | /api/v1/demo-data/execute/status | Poll progress of an in-flight `/demo-data/execute` call |
| DELETE | /api/v1/demo-data       | Delete runs created by the demo-data endpoints |
| GET    | /api/v1/health/db       | Database migration/readiness status |

## Demo walkthrough

Use this flow when you want the app to become meaningful immediately without manually running every scenario first.

1. Start the backend from `backend/` with `uvicorn app.main:app --reload`.
2. Start the frontend from `frontend/` with `npm run dev`.
3. Click **Demo data** in the header and **Add realistic evidence**. This is fast, deterministic, and makes no LLM calls — it inserts representative runs, checkpoints, human ratings, traces, and recommendation evidence for every runner and scenario (the "runs per runner per scenario" slider controls how many of each). The same modal's **Execute scenarios** option instead runs the scenarios through the real runners with a chosen LLM model, which can use tokens and take longer.
4. Open **Compare Scenarios**, filter by a scenario family, pick a scenario, and click **Run All Runners**. The comparison table shows the latest result from each abstraction level.
5. Select a run from the comparison table or History and expand **Trace** details. LangGraph-backed runners show `plan`, `act`, `decide`, and `finalize` node events with timing, token/cost data, and bounded message previews.
6. Open **Recommendations** for the same scenario. Review the primary/fallback strategy, simulated handled rates, cost/latency projection, runner evidence, and "why not this runner?" counterfactuals.
7. Open **Human Metrics** to inspect checkpoint, approval, rejection, escalation, and manual post-run evaluation signals.
8. Open **Demo data** again and click **Delete demo data** when you want to return to only real runs.

The same flow is available through the API with `POST /api/v1/demo-data`, `POST /api/v1/demo-data/execute`, `POST /api/v1/runs`, `GET /api/v1/recommendations/{scenario_id}`, and `DELETE /api/v1/demo-data`.

## Layout

```
app/
  core/        config, logging (request-ID correlation), middleware
  schemas/     Pydantic models (Scenario, RunResult, Metrics, Evaluation)
  runners/     one class per abstraction level; all implement BaseRunner
  services/    scenario YAML store, deterministic evaluation, execution
  api/v1/      route modules
scenarios/     scenario definitions (YAML)
tests/         API-level tests
```

## Current runners

| Name              | Level | Status |
|-------------------|-------|--------|
| rules             | 0     | implemented - regex extraction + keyword decision table |
| workflow          | 1     | implemented - explicit state machine (extract → classify → policy table) |
| llm               | 2     | implemented - single OpenRouter LLM call with structured JSON output |
| tool              | 3     | implemented - single OpenRouter LLM call with a family-specific tool (at most one round trip) |
| agent             | 4     | implemented - LangGraph plan → (act → plan)* → decide loop with the same family-specific tool |
| human_checkpoint  | 5     | implemented - same agent graph, but pauses via LangGraph `interrupt()` whenever the shared checkpoint policy fires (risky action, missing required field, low confidence, or conflicting signals) until a human approves/rejects via `POST /runs/{run_id}/decision` |

The app currently includes five scenario families:

- `customer_support`: triage incoming customer messages, extract order context, and choose the next support action.
- `policy_qa`: answer policy questions from a small in-memory policy corpus (`app/services/policy_docs.py`) without taking direct customer-impacting actions.
- `git_diff_review`: review a unified diff and produce a verdict (`approve` / `comment` / `request_changes`) plus structured findings (security, reliability, style, testing).
- `incident_triage`: classify operational alerts, infer severity and service context, and choose the next incident response action.
- `hiring_screening`: screen a resume against role requirements and recommend whether to advance, reject, or ask for more information.

The `llm`, `tool`, `agent`, and `human_checkpoint` runners call an LLM model through OpenRouter by default. Set `JEAI_OPENROUTER_API_KEY` in `.env` to enable that path. You can also set `JEAI_OPENAI_API_KEY` to enable direct OpenAI API models in the same model picker; these are exposed as `openai:<model>` and route to `JEAI_OPENAI_BASE_URL` instead of OpenRouter. If neither relevant key is set, runs against LLM-backed runners fail with a clear "not configured" error. The UI can choose a per-run model from curated OpenRouter free models and direct
OpenAI models (`app/services/llm_models.py`). `GET /api/v1/pricing` also returns list prices for several commercial Anthropic and Google models for cost comparison; those reference rows aren't selectable for runs. Levels 3-5 use family-specific tools: `lookup_order` for customer support, `search_policy` for policy QA, `read_file` (over a small mock repo in `app/services/repo_files.py`) for git diff review, `check_service_status` for incident triage, and `lookup_role_requirements` for hiring screening.

Level 5 pausing is governed by a shared checkpoint policy (`app/services/checkpoint_policy.py`), evaluated after each family's `decide` step. A run pauses for human approval if any of these trigger:

- **risky_action**: the proposed action is in the family's `RISKY_ACTIONS` set including the 5 high-impact `customer_support` actions (billing/shipping/general escalation, cancellation, password reset), `provide_policy_answer` for `policy_qa`, `request_changes` for `git_diff_review`, high-impact incident actions (`restart_service`, `rollback_deploy`, `page_oncall`) for `incident_triage`, or hiring decisions(`advance_to_interview`, `reject`) for `hiring_screening`.
- **missing_fields**: the proposed output is missing one of the scenario's `required_fields`.
- **low_confidence**: the model's self-reported `confidence` is below `confidence_threshold` (defaults to 0.7, overridable per scenario).
- **conflicting_signals**: the model needed one or more retries to produce a valid structured response.

For `git_diff_review`, only `request_changes` is risky, so `approve`/`comment` verdicts are posted automatically unless another trigger fires. For `policy_qa`, every answer is `provide_policy_answer` (always risky), so every
run pauses for review by default. The pending-approval payload includes a `triggers` list describing which check(s) fired and why, surfaced in the frontend's approval panel.

The recommendation engine analyzes recorded runs for a scenario and picks the lowest abstraction level that meets reliability thresholds (success rate and average score), using estimated cost and latency as tie-breakers. It can also recommend a blended strategy such as a low-level primary runner with a reliable fallback runner, and reports an operational complexity score.

For subjective Git Diff Review runs, `JEAI_LLM_JUDGE_ENABLED=true` enables an LLM-as-judge evaluation check that scores review usefulness and specificity in addition to deterministic scenario checks.

Every run also includes a lightweight trace timeline: request receipt, runner execution, tool calls exposed by the runner, checkpoints/decisions, errors, and evaluation. Trace events include timing, token, cost, and details payloads so the frontend can explain where latency and cost came from. LangGraph-backed runners additionally emit graph-node events for `plan`, `act`, `decide`, and `finalize`.

Post-run human evaluations can be saved on completed runs with a 1-5 score, useful/correct flags, and an optional comment. Recommendation simulations use historical runner rates to project primary/fallback/human-handled percentages, average cost, and average latency for blended strategies.

Additional docs:

- [Runner and scenario-family architecture](docs/architecture.md)
- [How to add a new scenario family](docs/add-scenario-family.md)
- [LangChain vs LangGraph in this app](docs/langchain-vs-langgraph.md)

## Conventions

- All settings come from env vars prefixed `JEAI_` (see `.env.example`).
- Every HTTP request gets an `X-Request-ID`; all log lines within a request carry it. Set `JEAI_LOG_JSON=true` for JSON logs in production.
- Runs and pending Level 5 approvals are stored in SQLite via SQLAlchemy (`app/db/models.py`). Configure the file path with `JEAI_DATABASE_PATH`; by default it uses `../data/just_enough_ai.sqlite3`, outside the watched `backend/` source tree so dev reload does not react to SQLite writes.
- Schema changes are managed with Alembic (`alembic/`). The app runs `alembic upgrade head` automatically on startup, so no manual migration step is needed. To add a new migration after changing `app/db/models.py`, run from `backend/`:
  ```powershell
  alembic revision --autogenerate -m "describe the change"
  ```
