"""Shared Hiring Screening vocabulary and parsing helpers."""

from __future__ import annotations

import re
from typing import Any

from app.services.checkpoint_policy import parse_confidence

ALLOWED_ACTIONS: dict[str, str] = {
    "advance_to_interview": "Move the candidate forward to an interview.",
    "reject": "Decline the application.",
    "request_more_info": "Ask the candidate for missing information.",
    "escalate_to_recruiter": "Flag the application for manual recruiter review.",
}

#: Here "decision" *is* the action — there's no separate intent/action split.
DECISION_LABELS = list(ALLOWED_ACTIONS)

#: Action a HumanCheckpointRunner falls back to if a risky proposal is
#: rejected by a human reviewer.
REJECT_ACTION = "escalate_to_recruiter"

#: The single role used by the deterministic rules/workflow runners and by
#: every shipped hiring_screening scenario.
ROLE_ID = "senior-backend-engineer"

REQUIRED_SKILLS = ["python", "aws", "postgresql", "kubernetes"]

SKILL_DISPLAY_NAMES: dict[str, str] = {
    "python": "Python",
    "aws": "AWS",
    "postgresql": "PostgreSQL",
    "kubernetes": "Kubernetes",
}

MIN_YEARS_EXPERIENCE = 5

ONCALL_KEYWORDS = ["on-call", "oncall"]

YEARS_RE = re.compile(r"(\d+)\+?\s*years?")


def extract_years_experience(resume_text: str) -> int | None:
    match = YEARS_RE.search(resume_text.lower())
    if not match:
        return None
    return int(match.group(1))


def score_resume(resume_text: str) -> dict[str, Any]:
    """Deterministically score a resume against ROLE_ID's requirements."""
    text = resume_text.lower()
    years = extract_years_experience(text)
    matched_skills = [skill for skill in REQUIRED_SKILLS if skill in text]
    missing_skills = [skill for skill in REQUIRED_SKILLS if skill not in matched_skills]
    has_oncall = any(keyword in text for keyword in ONCALL_KEYWORDS)
    match_score = round(100 * len(matched_skills) / len(REQUIRED_SKILLS))

    if years is None:
        decision = "request_more_info"
    elif not missing_skills and has_oncall and years >= MIN_YEARS_EXPERIENCE:
        decision = "advance_to_interview"
    elif len(missing_skills) >= 2 or years < MIN_YEARS_EXPERIENCE:
        decision = "reject"
    else:
        decision = "escalate_to_recruiter"

    return {
        "decision": decision,
        "match_score": match_score,
        "matched_requirements": [SKILL_DISPLAY_NAMES[skill] for skill in matched_skills],
        "missing_requirements": [SKILL_DISPLAY_NAMES[skill] for skill in missing_skills],
    }


# --- prompts ----------------------------------------------------------------

ACTION_LINES = "\n".join(f"- {name}: {desc}" for name, desc in ALLOWED_ACTIONS.items())

SYSTEM_PROMPT = f"""You are a resume screening assistant with access to a \
`lookup_role_requirements` tool that returns a role's required skills, minimum \
years of experience, and other requirements.

Look up the role's requirements (the role id is given in the input) before assessing \
the candidate. Then reply with ONLY a JSON object with these fields:
- "decision": the single most appropriate next step, one of:
{ACTION_LINES}
- "match_score": a number from 0 to 100 indicating how well the candidate matches the \
role's requirements
- "matched_requirements": a list of requirements the candidate meets
- "missing_requirements": a list of requirements the candidate does not meet
- "summary": a one-sentence summary of the assessment
- "confidence": a number from 0.0 to 1.0 indicating how confident you are in this decision

Reply with ONLY the JSON object — no markdown, no commentary."""

NO_CONTEXT_SYSTEM_PROMPT = f"""You are a resume screening assistant. You will be given a \
candidate's resume, including the role they're being considered for. You do not have \
access to the role's full requirements — base your assessment only on the resume text.

Reply with ONLY a JSON object with these fields:
- "decision": the single most appropriate next step, one of:
{ACTION_LINES}
- "match_score": a number from 0 to 100 indicating how well the candidate matches the role
- "matched_requirements": a list of requirements the candidate appears to meet
- "missing_requirements": a list of requirements the candidate appears to be missing
- "summary": a one-sentence summary of the assessment
- "confidence": a number from 0.0 to 1.0 indicating how confident you are in this decision

Reply with ONLY the JSON object — no markdown, no commentary."""

FINAL_ANSWER_PROMPT = "Now reply with ONLY the JSON object as specified."

FALLBACK_PROPOSAL: dict[str, Any] = {
    "output": {
        "decision": "escalate_to_recruiter",
        "match_score": 0,
        "matched_requirements": [],
        "missing_requirements": [],
        "summary": "Unable to complete a confident assessment.",
    },
    "actions": ["escalate_to_recruiter"],
    "action": "escalate_to_recruiter",
    "confidence": 0.0,
}


def parse_screening_proposal(
    data: dict[str, Any], role: dict[str, Any] | None = None
) -> dict[str, Any]:
    if "decision" not in data:
        raise KeyError("decision")

    decision = str(data.get("decision") or "").lower().replace(" ", "_")
    if decision not in ALLOWED_ACTIONS:
        decision = REJECT_ACTION

    try:
        match_score = int(data.get("match_score") or 0)
    except (TypeError, ValueError):
        match_score = 0
    match_score = max(0, min(100, match_score))

    matched = data.get("matched_requirements")
    missing = data.get("missing_requirements")
    matched_requirements = [str(item) for item in matched] if isinstance(matched, list) else []
    missing_requirements = [str(item) for item in missing] if isinstance(missing, list) else []

    summary = str(data.get("summary") or "")

    output: dict[str, Any] = {
        "decision": decision,
        "match_score": match_score,
        "matched_requirements": matched_requirements,
        "missing_requirements": missing_requirements,
        "summary": summary,
    }
    if role is not None:
        output["role"] = role

    confidence = parse_confidence(data.get("confidence"))
    return {"output": output, "actions": [decision], "action": decision, "confidence": confidence}
