"""
User registration management.

Mirrors the n8n flow:
  - Check if a Telegram user exists in the `users` table
  - If not, insert them before proceeding
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


def ensure_user_exists(
    user_id: int,
    chat_id: int,
    first_name: str = "",
    last_name: str = "",
    language_code: str = "en",
) -> bool:
    """
    Check if the user exists. If not, insert them.

    Returns:
        True if user was newly created, False if they already existed.
    """
    db = _get_client()

    result = (
        db.table("users")
        .select("user_id")
        .eq("user_id", user_id)
        .execute()
    )

    if result.data:
        return False  # Already exists

    # New user — insert their profile
    db.table("users").insert({
        "user_id": user_id,
        "chat_id": chat_id,
        "first_name": first_name,
        "last_name": last_name or "",
        "language_code": language_code or "en",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }).execute()

    logger.info(f"New user registered: {user_id} ({first_name} {last_name})")
    return True
