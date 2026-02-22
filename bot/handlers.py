"""
Telegram message handler.

This is the main entry point for every conversation turn. It orchestrates
the full pipeline that n8n handled visually:

  Receive message
    → Ensure user exists
    → Log user message
    → Save to minimal_context + trim
    → Load context for agent
    → Run agent
    → Log assistant reply
    → Save assistant reply to minimal_context + trim
    → Send reply to Telegram
"""

import logging

from telegram import Update
from telegram.ext import ContextTypes

import config
from bot.users import ensure_user_exists
from services.context import (
    log_message,
    save_to_context,
    trim_context,
    load_context,
    format_context_for_prompt,
)
from agent.runner import run_agent

logger = logging.getLogger(__name__)


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle an incoming Telegram text message."""

    # --- 1. Extract fields from the Telegram update ---
    message = update.message
    if not message or not message.text:
        return

    user_id = message.from_user.id
    chat_id = message.chat.id
    text = message.text
    message_id = message.message_id
    update_id = update.update_id
    first_name = message.from_user.first_name or ""
    last_name = message.from_user.last_name or ""
    language_code = message.from_user.language_code or "en"

    logger.info(f"Message from user {user_id} (chat {chat_id}): {text[:60]}")

    try:
        # --- 2. Register user if new ---
        ensure_user_exists(
            user_id=user_id,
            chat_id=chat_id,
            first_name=first_name,
            last_name=last_name,
            language_code=language_code,
        )

        # --- 3. Log the user message to chat_logs (permanent record) ---
        log_message(
            user_id=user_id,
            chat_id=chat_id,
            role="user",
            text=text,
            message_id=message_id,
            update_id=update_id,
        )

        # --- 4. Save user message to minimal_context and trim to limit ---
        save_to_context(
            user_id=user_id,
            chat_id=chat_id,
            role="user",
            text=text,
            message_id=message_id,
            update_id=update_id,
        )
        trim_context(user_id)

        # --- 5. Load the current context window for the agent ---
        context_messages = load_context(user_id)
        recent_conversation = format_context_for_prompt(context_messages)

        # --- 6. Run the agent ---
        reply = run_agent(user_message=text, recent_conversation=recent_conversation)

        # --- 7. Log the assistant reply to chat_logs ---
        log_message(
            user_id=user_id,
            chat_id=chat_id,
            role="assistant",
            text=reply,
            update_id=update_id,
        )

        # --- 8. Save assistant reply to minimal_context and trim again ---
        save_to_context(
            user_id=user_id,
            chat_id=chat_id,
            role="assistant",
            text=reply,
            update_id=update_id,
        )
        trim_context(user_id)

        # --- 9. Send the reply back to Telegram ---
        await message.reply_text(reply)

    except Exception as e:
        logger.error(f"Error handling message from user {user_id}: {e}", exc_info=True)
        await message.reply_text(
            "Sorry, something went wrong on my end. Please try again in a moment."
        )
