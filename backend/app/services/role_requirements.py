"""Mock role-requirements lookup used as a "tool" by the Tool/Agent/
HumanCheckpoint runners (Levels 3-5) for the hiring_screening family.
Standing in for a real ATS/HRIS API call."""

from typing import Any

ROLE_REQUIREMENTS: dict[str, dict[str, Any]] = {
    "senior-backend-engineer": {
        "role_id": "senior-backend-engineer",
        "title": "Senior Backend Engineer",
        "required_skills": ["Python", "AWS", "PostgreSQL", "Kubernetes"],
        "min_years_experience": 5,
        "required_experience": ["On-call rotation experience"],
        "nice_to_have": ["Go", "Terraform"],
    },
    "data-analyst": {
        "role_id": "data-analyst",
        "title": "Data Analyst",
        "required_skills": ["SQL", "Python", "Tableau"],
        "min_years_experience": 2,
        "required_experience": ["Stakeholder reporting experience"],
        "nice_to_have": ["dbt", "Looker"],
    },
}


def lookup_role_requirements(role_id: str) -> dict[str, Any] | None:
    """Return the requirements for a role, or None if no role with that ID exists."""
    return ROLE_REQUIREMENTS.get(role_id)


# OpenAI-compatible function-calling schema for the lookup_role_requirements
# tool, shared by every runner that gives the LLM tool access.
LOOKUP_ROLE_REQUIREMENTS_TOOL_SCHEMA: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "lookup_role_requirements",
        "description": (
            "Look up a role's requirements by ID, including required skills, "
            "minimum years of experience, and other expectations."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "role_id": {
                    "type": "string",
                    "description": "The role ID, e.g. 'senior-backend-engineer'.",
                }
            },
            "required": ["role_id"],
        },
    },
}
