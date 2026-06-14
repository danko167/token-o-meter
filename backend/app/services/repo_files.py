"""Small mock repository used as a "tool" by the Tool/Agent/HumanCheckpoint
runners (Levels 3-5) for the Git Diff Review scenario family. Standing in for
a real `read_file`/repo-browsing API."""

from typing import Any

REPO_FILES: dict[str, str] = {
    "app/config.py": ('DEBUG = False\nDATABASE_URL = "sqlite:///app.db"\n'),
    "app/payments.py": (
        "def calculate_total(price: float, quantity: int) -> float:\n"
        "    return price * quantity\n"
    ),
    "tests/test_payments.py": (
        "from app.payments import calculate_total\n"
        "\n\n"
        "def test_calculate_total():\n"
        "    assert calculate_total(10, 2) == 20\n"
    ),
    "app/users.py": (
        "def get_user_email(user_id: str) -> str:\n"
        '    return DB[user_id]["email"]\n'
    ),
    "app/notifications.py": (
        "from app.users import get_user_email\n"
        "\n\n"
        "def notify_user(user_id: str, message: str) -> None:\n"
        "    email = get_user_email(user_id)\n"
        "    send_email(email, message)\n"
    ),
}


def read_file(path: str) -> str | None:
    """Return the current contents of `path`, or None if it doesn't exist."""
    return REPO_FILES.get(path)


# OpenAI-compatible function-calling schema for the read_file tool, shared by
# every runner that gives the LLM repo access.
READ_FILE_TOOL_SCHEMA: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "read_file",
        "description": "Read the current contents of a file in the repository.",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Repository-relative file path, e.g. 'app/payments.py'.",
                }
            },
            "required": ["path"],
        },
    },
}
