# Just enough AI

Just enough AI runs the **same task** through six different implementation strategies - from plain regex/decision tables up to a LangGraph agent with a human-in-the-loop checkpoint - and lets you compare the results side by side:
output, actions taken, latency, token cost, retries, evaluation score, and (for the agentic levels) a full execution trace.

It's a FastAPI backend (`backend/`) plus a React/Vite/Mantine frontend (`frontend/`).

## Why this exists

There's been a lot of discussion lately about the cost of AI *while building* software - coding assistants, agentic IDEs, token-based pricing, usage limits. This project is about a different layer of that: the cost of AI
*inside* the software you build.

Not every problem needs an agent. Not every problem needs an LLM. Sometimes a workflow is enough. Sometimes a few rules are enough. And sometimes an agent is absolutely the right answer. The challenge is figuring out which is which.

Most discussions around AI start with: "Can an agent do this?"
This project is interested in a different question: "Should an agent do this at all?"

And if not, what is the cheapest reliable alternative?

The project started as "learn LangChain." It turned into something more useful: a way to make the *cost of abstraction* visible.

It's easy to reach for an LLM, then a tool-using LLM, then a multi-step agent, because each step feels like a small upgrade. It's much harder to see, in one place, what each step actually buys you - and what it costs in accuracy, latency, tokens, reliability, and human effort - versus just writing the rules.

Just enough AI answers that by running **6 levels** against the **same scenarios** and recording everything needed to compare them honestly:

| Level | Runner | What it is |
|-------|--------|------------|
| 0 | `rules` | Regex extraction + a keyword decision table. Fast, cheap, fully deterministic. |
| 1 | `workflow` | An explicit state machine: extract → classify → policy table. |
| 2 | `llm` | One structured LLM call, no tools. |
| 3 | `tool` | One LLM call that may use a single family-specific tool (at most one round trip). |
| 4 | `agent` | A LangGraph `plan -> (act -> plan)* -> decide -> finalize` loop with the same tool. |
| 5 | `human_checkpoint` | The Level 4 agent graph, but it can pause via LangGraph `interrupt()` and wait for a human decision before finalizing. |

Runner level and **scenario family** (the task domain) are independent axes - any runner can be pointed at any family:

- **`customer_support`** - triage a customer email, look up the order, and pick the next support action.
- **`policy_qa`** - answer a policy question from a small in-memory policy corpus, with citations.
- **`git_diff_review`** - review a unified diff and produce a verdict (`approve` / `comment` / `request_changes`) with structured findings.
- **`incident_triage`** - classify operational alerts, infer severity and service context, and choose the next incident response action.
- **`hiring_screening`** - screen a resume against role requirements and recommend whether to advance, reject, or ask for more information.

A recommendation engine then looks at recorded runs for a scenario and suggests the *cheapest abstraction level that's actually reliable enough* - sometimes a single low-level runner, sometimes a low-level primary with a
more capable fallback.

Every abstraction comes with a cost. Sometimes the answer is an agent. Sometimes it's a workflow. And sometimes it's a surprisingly boring piece of code.

## The Human Checkpoint Philosophy

A Level 5 run doesn't pause "because it's Level 5" or because of one hardcoded rule like "billing escalations always need approval." Instead, every proposed action is run through a shared **checkpoint policy** (`backend/app/services/checkpoint_policy.py`) that asks four concrete questions:
- **risky_action** - is this action in the family's high-impact set (e.g. cancel an order, reset a password, escalate billing)?
- **missing_fields** - is the model's output missing information the scenario says it needs (`required_fields`)?
- **low_confidence** - did the model report a confidence below the threshold (default `0.7`, overridable per scenario)?
- **conflicting_signals** - did the model need retries to produce a valid response at all?

If any of these fire, the run pauses with a `pending_approval` status and a list of *which* checks fired and *why* — shown to the reviewer as badges in the frontend, not a black-box "needs approval" flag. A human approves or
rejects via `POST /runs/{run_id}/decision`, and the graph resumes from exactly where it left off.

The point isn't "always ask a human" - it's making the *trigger* for asking explicit, inspectable, and reusable across every scenario family.

## Quickstart

```powershell
# Backend
cd backend
py -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
copy .env.example .env   # add JEAI_OPENROUTER_API_KEY or JEAI_OPENAI_API_KEY to enable levels 2-5
uvicorn app.main:app --reload

# Frontend (separate shell)
cd frontend
npm install
copy .env.example .env
npm run dev
```

Open the frontend (usually http://localhost:5173), click **Demo data** in the header, and **Add realistic evidence** (fast, deterministic, no LLM calls). Then:

1. **Run Scenario** - pick `customer-email-triage` and the `rules` runner, then re-run it with `human_checkpoint`. Same input, very different output/cost/trace.
2. **Compare Scenarios** - run every level against one scenario and see the table fill in: output, actions, tokens, cost, retries, evaluation score.
3. **History** - every run is persisted; reopen any of them, including `pending_approval` runs awaiting a decision.
4. **Recommendations** - see which level the recorded evidence actually justifies for that scenario.
5. **Human Metrics** - aggregate checkpoint/approval/rejection/escalation rates across runs.

Without `JEAI_OPENROUTER_API_KEY` or `JEAI_OPENAI_API_KEY` set, levels 2-5 fail with a clear "not configured" error - levels 0-1 work with no API key at all.

## Project layout

```
backend/
FastAPI app, runners (one per level), LangGraph agent graphs, scenario YAML, evaluation/recommendation services, SQLite storage
frontend/
React + Vite + Mantine UI: run/compare/history/recommendations/ human-metrics tabs
```

See [backend/README.md](backend/README.md) and [frontend/README.md](frontend/README.md) for setup, API surface, and UI details, and [backend/docs/](backend/docs/) for the runner/scenario-family architecture and the LangChain-vs-LangGraph design notes.