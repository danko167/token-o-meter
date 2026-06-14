"""Mock order database used as a "tool" by the Tool/Agent/HumanCheckpoint
runners (Levels 3-5). Standing in for a real orders API or database call."""

from typing import Any

ORDERS: dict[str, dict[str, Any]] = {
    "1234": {
        "order_id": "1234",
        "status": "delivered",
        "placed_at": "2026-05-20",
        "delivered_at": "2026-05-24",
        "total_usd": 89.98,
        "items": ["Wireless Mouse", "USB-C Cable"],
        "charge_count": 2,
        "carrier": "UPS",
        "tracking_number": "1Z999AA10123456784",
    },
    "5678": {
        "order_id": "5678",
        "status": "in_transit",
        "placed_at": "2026-06-01",
        "delivered_at": None,
        "total_usd": 45.50,
        "items": ["Phone Case"],
        "charge_count": 1,
        "carrier": "FedEx",
        "tracking_number": "9400111108296123456789",
        "estimated_delivery": "2026-06-12",
    },
}


def lookup_order(order_id: str) -> dict[str, Any] | None:
    """Return order details, or None if no order with that ID exists."""
    return ORDERS.get(order_id)


# OpenAI-compatible function-calling schema for the lookup_order tool, shared by
# every runner that gives the LLM tool access.
LOOKUP_ORDER_TOOL_SCHEMA: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "lookup_order",
        "description": (
            "Look up an order by ID to get its status, tracking number, "
            "carrier, items, and how many times it was charged."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "order_id": {
                    "type": "string",
                    "description": "The numeric order ID, without the '#' prefix.",
                }
            },
            "required": ["order_id"],
        },
    },
}
