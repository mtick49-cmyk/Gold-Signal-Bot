"""Standalone Telegram connectivity check.

Run as its own GitHub Actions step, before the main signal bot starts,
so a broken token/chat ID fails fast and visibly instead of silently
preventing every future signal from being delivered.
"""
from __future__ import annotations

import logging
import os
import sys

from telegram_service import test_connection

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s - %(message)s")
logger = logging.getLogger("gold_signal_bot.telegram_test")


def main() -> None:
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")

    if not token or not chat_id:
        print("TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID is missing.")
        sys.exit(1)

    if test_connection(token, chat_id):
        logger.info("Telegram test passed.")
        sys.exit(0)

    logger.error("Telegram test failed.")
    sys.exit(1)


if __name__ == "__main__":
    main()
