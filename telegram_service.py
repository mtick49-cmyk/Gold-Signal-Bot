"""Telegram Bot API integration.

Every call goes through send_message(), which always inspects the HTTP
status and JSON body before reporting success. Nothing is assumed to have
been delivered just because the HTTP request did not raise an exception.
"""
from __future__ import annotations

import logging

import requests

logger = logging.getLogger("gold_signal_bot.telegram")

TELEGRAM_API_URL = "https://api.telegram.org/bot{token}/{method}"
REQUEST_TIMEOUT_SECONDS = 15

_STATUS_EXPLANATIONS = {
    400: "400 = invalid request (often a bad chat ID).",
    401: "401 = invalid or revoked bot token.",
    403: "403 = bot is blocked by the user, kicked from the chat, or lacks permission.",
    404: "404 = wrong endpoint or malformed token.",
    429: "429 = rate limited by Telegram, back off before retrying.",
}


def _mask(token: str | None) -> str:
    if not token or len(token) < 8:
        return "****"
    return f"{token[:4]}...{token[-4:]}"


def _explain_status(status_code: int) -> None:
    if status_code in _STATUS_EXPLANATIONS:
        logger.error(_STATUS_EXPLANATIONS[status_code])
    elif status_code >= 500:
        logger.error("%s = Telegram server error, likely temporary.", status_code)


def send_message(token: str, chat_id: str, text: str) -> bool:
    """Send a message via the Telegram Bot API.

    Returns True only if Telegram confirms the message was accepted
    (HTTP 200 and {"ok": true} in the response body). Returns False on
    any failure, and logs the HTTP status + response body for debugging.
    Never raises on Telegram-side errors -- callers decide what to do
    with a False result.
    """
    url = TELEGRAM_API_URL.format(token=token, method="sendMessage")
    payload = {"chat_id": chat_id, "text": text}

    try:
        response = requests.post(url, json=payload, timeout=REQUEST_TIMEOUT_SECONDS)
    except requests.exceptions.RequestException as exc:
        logger.error("Telegram request failed (network error): %s", exc)
        return False

    try:
        response_json = response.json()
    except ValueError:
        response_json = {"raw_text": response.text}

    if response.status_code == 200 and response_json.get("ok") is True:
        logger.info("Telegram message sent successfully.")
        return True

    logger.error(
        "Telegram API error:\nHTTP status: %s\nResponse: %s",
        response.status_code, response_json,
    )
    _explain_status(response.status_code)
    return False


def test_connection(token: str, chat_id: str) -> bool:
    """Send a lightweight connectivity test message."""
    logger.info("Testing Telegram connection (token=%s)...", _mask(token))
    return send_message(token, chat_id, "✅ Telegram connection test successful.")
