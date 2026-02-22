"""
Manages conversation context in Supabase.

Tables used:
  - chat_logs       : Full permanent log of every message
  - minimal_context : Rolling window of last N messages used as agent context
"""

import logging
from datetime import datetime, timezone

from supabase import create_client, Client
import config

logger = logging.getLogger(__name__)

_client: Client | None = None


def _get_client() -> Client:
    global _client
    if _client is None:
        _client = create_client(config.SUPABASE_URL, config.SUPABASE_SERVICE_KEY)
    return _client


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

def log_message(user_id: int, chat_id: int, role: str, text: str,
                message_id: int | None = None, update_id: int | None = None) -> None:
    """Append a message to the permanent chat_logs table."""
    db = _get_client()
    db.table("chat_logs").insert({
        "user_id": user_id,
        "chat_id": chat_id,
        "role": role,
        "text": text,
        "message_id": message_id,
        "update_id": update_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }).execute()


# ---------------------------------------------------------------------------
# Minimal Context (rolling window)
# ---------------------------------------------------------------------------

def save_to_context(user_id: int, chat_id: int, role: str, text: str,
                    message_id: int | None = None, update_id: int | None = None) -> None:
    """Insert a message into the minimal_context rolling window."""
    db = _get_client()
    db.table("minimal_context").insert({
        "user_id": user_id,
        "chat_id": chat_id,
        "role": role,
        "text": text,
        "message_id": message_id,
        "update_id": update_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }).execute()


def trim_context(user_id: int) -> None:
    """Call the Supabase RPC to trim minimal_context to the last N messages."""
    db = _get_client()
    db.rpc("trim_minimal_context", {"p_user_id": user_id}).execute()


def load_context(user_id: int) -> list[dict]:
    """
    Fetch the current minimal_context for a user, sorted oldest→newest,
    ready to be injected into the system prompt.
    """
    db = _get_client()
    result = (
        db.table("minimal_context")
        .select("role, text, timestamp")
        .eq("user_id", user_id)
        .order("timestamp", desc=False)
        .execute()
    )
    return result.data or []


def format_context_for_prompt(messages: list[dict]) -> str:
    """Convert context rows into the string the system prompt expects."""
    if not messages:
        return "(No previous conversation)"
    lines = [f"{m['role']}: {m['text']}" for m in messages]
    return "\n".join(lines)
