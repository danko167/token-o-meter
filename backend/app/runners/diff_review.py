"""Shared Git Diff Review vocabulary and parsing helpers."""

from __future__ import annotations

import re
from typing import Any

from app.services.checkpoint_policy import parse_confidence

# --- diff parsing ------------------------------------------------------------


def parse_diff(diff_text: str) -> list[dict[str, Any]]:
    """Split a unified diff into per-file added lines."""
    files: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None

    for line in diff_text.splitlines():
        if line.startswith("+++ "):
            path = line[len("+++ ") :].strip()
            if path.startswith("b/"):
                path = path[2:]
            current = {"path": path, "added_lines": []}
            files.append(current)
        elif line.startswith("+") and not line.startswith("+++") and current is not None:
            current["added_lines"].append(line[1:])

    return files


# --- static analysis ----------------------------------------------------------

# (category, severity, pattern, message); checked against every added line.
FINDING_RULES: list[tuple[str, str, re.Pattern[str], str]] = [
    (
        "hardcoded_secret",
        "blocker",
        re.compile(r'(?i)(api_key|secret|password|token)\s*=\s*["\'][^"\']{8,}["\']'),
        "Hardcoded credential found",
    ),
    (
        "eval_usage",
        "blocker",
        re.compile(r"\b(eval|exec)\("),
        "Use of eval/exec is a security risk",
    ),
    (
        "unsafe_sql",
        "blocker",
        re.compile(r"(?i)(select|insert|update|delete).*(\{.*\}|%s|format\(|\+)", re.DOTALL),
        "String-built SQL query may allow injection",
    ),
    (
        "bare_except",
        "warning",
        re.compile(r"except\s*:"),
        "Bare except clause swallows all errors",
    ),
    (
        "debug_print",
        "nit",
        re.compile(r"\bprint\("),
        "Debug print statement left in code",
    ),
]

CATEGORY_GROUP: dict[str, str] = {
    "hardcoded_secret": "security",
    "eval_usage": "security",
    "unsafe_sql": "security",
    "bare_except": "reliability",
    "debug_print": "style",
    "missing_tests": "testing",
}

_SEVERITY_RANK = {"blocker": 0, "warning": 1, "nit": 2}


def run_static_checks(diff_text: str) -> list[dict[str, str]]:
    """Run regex-based checks against every added line, plus a missing-tests
    check at the diff level."""
    files = parse_diff(diff_text)
    findings: list[dict[str, str]] = []

    for file in files:
        for line in file["added_lines"]:
            for category, severity, pattern, message in FINDING_RULES:
                if pattern.search(line):
                    findings.append(
                        {"category": category, "severity": severity, "message": message}
                    )

    changed_paths = [file["path"] for file in files]
    touches_non_test_python = any(
        path.endswith(".py") and "test" not in path for path in changed_paths
    )
    touches_tests = any("test" in path for path in changed_paths)
    if touches_non_test_python and not touches_tests:
        findings.append(
            {
                "category": "missing_tests",
                "severity": "warning",
                "message": "This diff changes a Python module but no test file.",
            }
        )

    return findings


def classify_category(findings: list[dict[str, str]]) -> str:
    """Category group of the highest-severity finding, or 'clean' if none."""
    if not findings:
        return "clean"
    highest = min(findings, key=lambda f: _SEVERITY_RANK.get(f["severity"], 99))
    return CATEGORY_GROUP.get(highest["category"], "general")


def verdict_from_findings(findings: list[dict[str, str]]) -> str:
    severities = {f["severity"] for f in findings}
    if "blocker" in severities:
        return "request_changes"
    if findings:
        return "comment"
    return "approve"


VERDICT_TO_ACTION: dict[str, str] = {
    "approve": "approve_pr",
    "comment": "comment_on_pr",
    "request_changes": "request_changes",
}

#: Action a HumanCheckpointRunner falls back to if a "request_changes"
#: proposal is rejected by a human reviewer.
REJECT_ACTION = "comment_on_pr"


# --- prompts --------------------------------------------------------------

SYSTEM_PROMPT = """You are an automated code reviewer with access to a `read_file` tool that \
returns the current contents of any file in the repository. You will be given a unified diff.

Use read_file to check related files (e.g. existing tests, or files that call a changed \
function) before reviewing. Then reply with ONLY a JSON object with these fields:
- "verdict": one of "approve", "comment", "request_changes"
- "findings": a list of objects, each with "category", "severity" (one of "blocker", \
"warning", "nit"), and "message"
- "summary": a one-sentence summary of the review
- "action": "approve_pr", "comment_on_pr", or "request_changes" (matching verdict)
- "confidence": a number from 0.0 to 1.0 indicating how confident you are in this verdict

Reply with ONLY the JSON object — no markdown, no commentary."""

NO_CONTEXT_SYSTEM_PROMPT = """You are an automated code reviewer. You will be given a unified \
diff. You do not have access to the rest of the repository — base your review only on the \
diff itself.

Reply with ONLY a JSON object with these fields:
- "verdict": one of "approve", "comment", "request_changes"
- "findings": a list of objects, each with "category", "severity" (one of "blocker", \
"warning", "nit"), and "message"
- "summary": a one-sentence summary of the review
- "action": "approve_pr", "comment_on_pr", or "request_changes" (matching verdict)

Reply with ONLY the JSON object — no markdown, no commentary."""

FINAL_ANSWER_PROMPT = "Now reply with ONLY the JSON object as specified."

FALLBACK_PROPOSAL: dict[str, Any] = {
    "output": {
        "verdict": "comment",
        "findings": [],
        "summary": "Unable to complete a confident review.",
    },
    "actions": ["comment_on_pr"],
    "action": "comment_on_pr",
    "confidence": 0.0,
}


def parse_diff_review_proposal(
    data: dict[str, Any], files_read: list[str] | None = None
) -> dict[str, Any]:
    if "verdict" not in data:
        raise KeyError("verdict")

    verdict = str(data.get("verdict") or "comment").lower().replace(" ", "_")
    if verdict not in VERDICT_TO_ACTION:
        verdict = "comment"

    findings: list[dict[str, str]] = []
    raw_findings = data.get("findings")
    if isinstance(raw_findings, list):
        for item in raw_findings:
            if not isinstance(item, dict):
                continue
            findings.append(
                {
                    "category": str(item.get("category") or "general"),
                    "severity": str(item.get("severity") or "nit"),
                    "message": str(item.get("message") or ""),
                }
            )

    summary = str(data.get("summary") or "")
    action = VERDICT_TO_ACTION[verdict]

    output: dict[str, Any] = {"verdict": verdict, "findings": findings, "summary": summary}
    if files_read:
        output["files_read"] = list(files_read)

    confidence = parse_confidence(data.get("confidence"))
    return {"output": output, "actions": [action], "action": action, "confidence": confidence}
