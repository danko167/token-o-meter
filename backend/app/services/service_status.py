"""Mock service status/metrics endpoint used as a "tool" by the Tool/Agent/
HumanCheckpoint runners (Levels 3-5) for the incident_triage family. Standing
in for a real observability/metrics API call."""

from typing import Any

SERVICE_STATUS: dict[str, dict[str, Any]] = {
    "checkout-api": {
        "service": "checkout-api",
        "status": "degraded",
        "error_rate_percent": 8.2,
        "p99_latency_ms": 2150,
        "cpu_percent": 61,
        "memory_percent": 58,
        "last_deploy_version": "v2.14.0",
        "minutes_since_deploy": 12,
    },
    "recommendation-worker": {
        "service": "recommendation-worker",
        "status": "degraded",
        "error_rate_percent": 0.4,
        "p99_latency_ms": 410,
        "cpu_percent": 39,
        "memory_percent": 92,
        "memory_trend": "climbing for 6 hours",
        "minutes_since_deploy": 7200,
    },
    "auth-service": {
        "service": "auth-service",
        "status": "healthy",
        "error_rate_percent": 0.0,
        "p99_latency_ms": 180,
        "cpu_percent": 22,
        "memory_percent": 35,
        "minutes_since_deploy": 4320,
        "recent_incident": "30s latency spike to 1500ms at 02:14 UTC, recovered by 02:15",
    },
}


def check_service_status(service: str) -> dict[str, Any] | None:
    """Return current status/metrics for a service, or None if unknown."""
    return SERVICE_STATUS.get(service)


# OpenAI-compatible function-calling schema for the check_service_status tool,
# shared by every runner that gives the LLM tool access.
CHECK_SERVICE_STATUS_TOOL_SCHEMA: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "check_service_status",
        "description": (
            "Look up a service's current status, including error rate, p99 "
            "latency, CPU/memory usage, and recent deploy or incident history."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "service": {
                    "type": "string",
                    "description": "The service name, e.g. 'checkout-api'.",
                }
            },
            "required": ["service"],
        },
    },
}
