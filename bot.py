"""Gold-Signal-Bot entry point.

Scans every configured symbol for RSI + MACD crossover signals on the M5
timeframe and sends alerts to Telegram. Designed to run as a short-lived
process inside a GitHub Actions workflow, triggered on a schedule.

This process intentionally does NOT run forever: it scans, sleeps a
little, scans again, and exits cleanly after config.RUN_SECONDS so the
next scheduled workflow run can pick up where it left off.
"""
from __future__ import annotations

import logging
import os
import sys
import time

import config
import state_manager
from signal_engine import process_symbol
from telegram_service import send_message

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s - %(message)s",
)
logger = logging.getLogger("gold_signal_bot")


def load_credentials() -> tuple[str, str]:
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        print("TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID is missing.")
        sys.exit(1)
    return token, chat_id


def send_startup_message(token: str, chat_id: str) -> None:
    message = (
        "🤖 Gold Signal Bot Started\n\n"
        "Timeframe: M5\n"
        "Markets: Forex + XAUUSD + BTCUSD"
    )
    if not send_message(token, chat_id, message):
        logger.error("Failed to send startup message. Aborting.")
        sys.exit(1)


def main() -> None:
    token, chat_id = load_credentials()
    send_startup_message(token, chat_id)

    state = state_manager.load_state(config.STATE_FILE)

    start_time = time.monotonic()
    scan_number = 0

    while True:
        scan_number += 1
        logger.info("--- Starting scan #%d ---", scan_number)

        for symbol, yahoo_symbol in config.SYMBOLS.items():
            try:
                process_symbol(symbol, yahoo_symbol, token, chat_id, state)
            except Exception as exc:
                # One bad symbol must never take down the whole run.
                logger.error(
                    "Unexpected error while processing %s: %s", symbol, exc, exc_info=True
                )
            finally:
                state_manager.save_state(config.STATE_FILE, state)

        elapsed = time.monotonic() - start_time
        if elapsed >= config.RUN_SECONDS:
            logger.info("Reached runtime limit (%.0fs), exiting cleanly.", elapsed)
            break

        remaining = config.RUN_SECONDS - elapsed
        sleep_time = min(config.CHECK_INTERVAL_SECONDS, max(0.0, remaining))
        if sleep_time <= 0:
            break
        logger.info("Sleeping %.0fs before next scan...", sleep_time)
        time.sleep(sleep_time)

    logger.info("Bot run complete. Exiting with code 0.")
    sys.exit(0)


if __name__ == "__main__":
    main()
