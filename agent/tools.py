"""
Tool definitions for the Claude agent.

Two responsibilities:
  1. TOOL_SCHEMAS  - The JSON schema definitions Claude reads to know what
                     tools exist and when to use them.
  2. execute_tool  - The dispatcher that receives Claude's tool call and
                     routes it to the correct Python function.
"""

import json
import logging

from services import rag, calendar as cal

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Tool Schemas (what Claude sees)
# ---------------------------------------------------------------------------

TOOL_SCHEMAS = [
    {
        "name": "search_knowledge_base",
        "description": (
            "Search the Verde Valley knowledge base for information about properties, "
            "amenities, policies, activities, and general guest questions. "
            "Use this for any question that doesn't require checking calendars or making bookings."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The search query, e.g. 'pet policy at Olive Lodge' or 'check-in time'",
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "check_availability",
        "description": (
            "Check if a specific property is available for a given date range. "
            "Use this when a guest asks whether a property is free on certain dates."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "property_name": {
                    "type": "string",
                    "description": (
                        "Exact property name. Must be one of: "
                        "'The Glasshouse', 'The River Cottage', 'The Olive Lodge', "
                        "'The Barn Loft', \"The Potter's Cabin\", \"The Stargazer's Pod\""
                    ),
                },
                "check_in_date": {
                    "type": "string",
                    "description": "Check-in date in YYYY-MM-DD format",
                },
                "check_out_date": {
                    "type": "string",
                    "description": "Check-out date in YYYY-MM-DD format",
                },
            },
            "required": ["property_name", "check_in_date", "check_out_date"],
        },
    },
    {
        "name": "create_booking",
        "description": (
            "Create a booking for a guest at a specific property. "
            "Only use this after confirming availability. "
            "Always collect guest name and email before calling this tool."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "property_name": {
                    "type": "string",
                    "description": "Exact property name (same options as check_availability)",
                },
                "check_in_date": {
                    "type": "string",
                    "description": "Check-in date in YYYY-MM-DD format",
                },
                "check_out_date": {
                    "type": "string",
                    "description": "Check-out date in YYYY-MM-DD format",
                },
                "guest_name": {
                    "type": "string",
                    "description": "Full name of the guest",
                },
                "guest_email": {
                    "type": "string",
                    "description": "Guest's email address",
                },
                "guest_phone": {
                    "type": "string",
                    "description": "Guest's phone number (optional)",
                },
            },
            "required": ["property_name", "check_in_date", "check_out_date", "guest_name", "guest_email"],
        },
    },
    {
        "name": "cancel_booking",
        "description": (
            "Cancel an existing booking. "
            "Use this when a guest asks to cancel their reservation. "
            "Try to extract guest name and booking details from the conversation before asking."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "property_name": {
                    "type": "string",
                    "description": "Exact property name (same options as check_availability)",
                },
                "guest_name": {
                    "type": "string",
                    "description": "Full name of the guest whose booking should be cancelled",
                },
                "check_in_date": {
                    "type": "string",
                    "description": "Check-in date of the booking to cancel in YYYY-MM-DD format",
                },
            },
            "required": ["property_name", "guest_name", "check_in_date"],
        },
    },
]


# ---------------------------------------------------------------------------
# Tool Dispatcher
# ---------------------------------------------------------------------------

def execute_tool(tool_name: str, tool_input: dict) -> str:
    """
    Receive a tool call from Claude, run the matching function,
    and return the result as a JSON string.
    """
    logger.info(f"Executing tool: {tool_name} | Input: {tool_input}")

    try:
        if tool_name == "search_knowledge_base":
            result = rag.search_knowledge_base(query=tool_input["query"])

        elif tool_name == "check_availability":
            result = cal.check_availability(
                property_name=tool_input["property_name"],
                check_in_date=tool_input["check_in_date"],
                check_out_date=tool_input["check_out_date"],
            )

        elif tool_name == "create_booking":
            result = cal.create_booking(
                property_name=tool_input["property_name"],
                check_in_date=tool_input["check_in_date"],
                check_out_date=tool_input["check_out_date"],
                guest_name=tool_input["guest_name"],
                guest_email=tool_input.get("guest_email", ""),
                guest_phone=tool_input.get("guest_phone", ""),
            )

        elif tool_name == "cancel_booking":
            result = cal.cancel_booking(
                property_name=tool_input["property_name"],
                guest_name=tool_input["guest_name"],
                check_in_date=tool_input["check_in_date"],
            )

        else:
            result = {"error": f"Unknown tool: {tool_name}"}

    except Exception as e:
        logger.error(f"Tool execution error ({tool_name}): {e}")
        result = {"error": f"Tool failed: {str(e)}"}

    # Always return a string back to Claude
    return json.dumps(result) if isinstance(result, dict) else str(result)
