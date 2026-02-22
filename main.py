"""
Verde Valley Stays — Telegram AI Concierge Bot
Entry point. Run this file to start the bot.

    python main.py
"""

import logging

from telegram.ext import ApplicationBuilder, MessageHandler, filters

import config
from bot.handlers import handle_message

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    level=logging.INFO,
)
# Quieten noisy third-party loggers
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("googleapiclient").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Bot startup
# ---------------------------------------------------------------------------

def main() -> None:
    config.validate()  # Crash early if any env vars are missing
    logger.info("Starting Verde Valley Stays bot...")

    app = ApplicationBuilder().token(config.TELEGRAM_TOKEN).build()

    # Route all plain text messages to the main handler
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logger.info("Bot is running. Press Ctrl+C to stop.")
    app.run_polling()


if __name__ == "__main__":
    main()
