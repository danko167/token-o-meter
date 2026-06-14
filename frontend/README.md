# Just enough AI — Frontend

React + TypeScript + Vite app for running scenarios against the Abstraction Bench backend, comparing results across abstraction levels (rules → LLM → agents), and reviewing run history, recommendations, and human-in-the-loop
metrics. See `../backend/README.md` for the full project overview and API.

## Setup

```powershell
npm install
copy .env.example .env
```

`VITE_API_BASE_URL` (see `.env.example`) points at the backend API and defaults to `http://localhost:8000/api/v1`.

## Run

```powershell
npm run dev
```

Vite prints the local URL, usually http://localhost:5173. The backend must be running separately (`uvicorn app.main:app --reload` from `backend/`).

## Build, lint & typecheck

```powershell
npm run build
npm run lint
```

`npm run build` runs `tsc -b` followed by `vite build`.

## Layout

```
src/
  api/         typed client + per-resource fetchers (scenarios, runners, runs, recommendations, human metrics, demo data, health)
  hooks/       TanStack Query hooks wrapping the API client
  components/  shared UI (run result panel, comparison table, history table, ...)
  pages/       one component per tab (Run, Compare, History, Recommendations, Human Metrics)
  lib/         small helpers (scenario family filters, runner level metadata, logging)
```

## Header

- **Levels** - opens a modal explaining the L0-L5 abstraction-level spectrum (one row per runner, with its label, color, and description) referenced by the badges shown throughout Run Scenario, Compare Scenarios, History, and Recommendations.
- **Model prices** - opens a modal listing the curated OpenRouter and direct OpenAI models available in the run dropdown (with per-million-token costs) alongside reference-only commercial Anthropic/Google model prices for cost comparison.
- **Demo data** - opens a modal to seed or remove demo runs across all dashboards. **Add realistic evidence** is fast, deterministic, and makes no LLM calls; **Execute scenarios** instead runs the scenarios through the real runners with a chosen LLM model and shows live progress while it runs. A shared slider controls how many runs per runner per scenario either option creates. **Delete demo data** removes runs created either way.
- **Token-o-meter** - a popover summarizing token usage and estimated spend across recorded run history (including demo runs), broken down by model and by runner.

## Pages

- **Run Scenario** - pick a scenario and a runner, execute it, and inspect the result: output, recommended actions, trace timeline, evaluation score, and (for Level 5) a pending-approval panel. Use **Add** beside the scenario picker to create or delete custom SQLite-backed scenarios inside the existing families. The "Est. cost" stat has a "View" link showing what this run's tokens would cost on commercial reference models.
- **Compare Scenarios** - run every runner against the same scenario and compare output, metrics, and evaluation side by side. Each row's "Cost" column also has a "View" link with the same commercial cost comparison.
- **History** - browse past runs and reopen any of them in the result panel. Select rows (or "select all") to bulk-archive (hidden from the default view, toggle "Show archived" to bring them back) or permanently delete with confirmation.
- **Recommendations** - for a scenario, show the recommended runner/strategy, projected cost/latency, supporting evidence, and counterfactuals.
- **Human Metrics** - aggregate checkpoint, approval, rejection, escalation, and human-evaluation signals across runs.

## Human checkpoint UI

`RunResultPanel` renders `pending_approval` runs (Level 5, `human_checkpoint`) with an approval/rejection control. The reason a run paused is shown as one badge per triggered check - `risky_action`, `missing_fields`, `low_confidence`, `conflicting_signals` - each with the corresponding human-readable explanation from the backend's
`checkpoint_policy`. If a run's `pending_approval.details` doesn't contain a `triggers` array (e.g. older demo data), the raw JSON details are shown instead.

## Conventions

- API requests go through `src/api/client.ts`, which reads `VITE_API_BASE_URL` and surfaces backend errors as a typed `ApiError`.
- Server state is managed with TanStack Query (`src/hooks/`); avoid duplicating fetched data in component state except for local UI selections.
- UI components use Mantine; prefer existing primitives (`Card`, `Stack`, `Group`, `Badge`, etc.) over custom CSS.
