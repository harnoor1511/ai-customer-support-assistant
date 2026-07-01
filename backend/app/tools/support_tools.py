"""
Tool (function-calling) definitions for the support assistant.

Each tool has:
- a schema (name, description, parameters) sent to the LLM so it knows
  what it can call and with what arguments
- a Python function that actually executes it against mock_db_service

Keeping this separate from llm_service.py means adding a new tool later
is just: write the function in mock_db_service, describe it here, done.
"""
from typing import Any

from app.services import mock_db_service

# --- Tool schemas (OpenAI/Gemini-compatible function-calling format) ---

TOOL_SCHEMAS = [
    {
        "name": "get_order",
        "description": "Look up an order by its order ID to get status, product, dates, and amount.",
        "parameters": {
            "type": "object",
            "properties": {
                "order_id": {"type": "string", "description": "The order ID, e.g. ORD-1001"},
            },
            "required": ["order_id"],
        },
    },
    {
        "name": "check_refund_eligibility",
        "description": "Check if an order is eligible for a refund based on delivery date and refund window.",
        "parameters": {
            "type": "object",
            "properties": {
                "order_id": {"type": "string", "description": "The order ID, e.g. ORD-1001"},
            },
            "required": ["order_id"],
        },
    },
    {
        "name": "search_knowledge_base",
        "description": "Search internal help articles for relevant information (e.g. policies, how-tos).",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search keywords, e.g. 'refund policy'"},
            },
            "required": ["query"],
        },
    },
    {
        "name": "create_support_ticket",
        "description": "Create a support ticket for a human agent to follow up on. Use only when the issue genuinely needs a human.",
        "parameters": {
            "type": "object",
            "properties": {
                "summary": {"type": "string", "description": "Short summary of the issue."},
                "priority": {"type": "string", "enum": ["P0", "P1", "P2", "P3"]},
                "customer_email": {"type": "string", "description": "Customer's email if known."},
            },
            "required": ["summary", "priority"],
        },
    },
]

# --- Dispatch table: tool name -> actual Python function ---

def execute_tool(name: str, arguments: dict[str, Any]) -> Any:
    """Run the requested tool and return its result (JSON-serializable)."""
    if name == "get_order":
        return mock_db_service.get_order(arguments["order_id"])
    if name == "check_refund_eligibility":
        return mock_db_service.check_refund_eligibility(arguments["order_id"])
    if name == "search_knowledge_base":
        return mock_db_service.search_knowledge_base(arguments["query"])
    if name == "create_support_ticket":
        return mock_db_service.create_support_ticket(
            summary=arguments["summary"],
            priority=arguments["priority"],
            customer_email=arguments.get("customer_email"),
        )
    raise ValueError(f"Unknown tool: {name}")