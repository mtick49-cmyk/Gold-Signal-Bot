"""Persist active signals and already-sent signal keys to a JSON file.

GitHub Actions runners are thrown away after every job, so state has to
live somewhere durable. This module writes state.json, which the
workflow commits back to the repository after each run (see
.github/workflows/main.yml). No secrets are ever stored here.
"""
from __future__ import annotations

import json
import logging
import os
from typing import Any

logger = logging.getLogger("gold_signal_bot.state")

DEFAULT_STATE: dict[str, Any] = {"active_signals": {}, "processed_candles": {}}


def load_state(path: str) -> dict[str, Any]:
    if not os.path.exists(path):
        logger.info("No existing state file at %s, starting fresh.", path)
        return {"active_signals": {}, "processed_candles": {}}

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("State file corrupt or unreadable (%s), starting fresh.", exc)
        return {"active_signals": {}, "processed_candles": {}}

    if not isinstance(data, dict):
        logger.warning("State file had unexpected shape, starting fresh.")
        return {"active_signals": {}, "processed_candles": {}}

    data.setdefault("active_signals", {})
    data.setdefault("processed_candles", {})
    return data


def save_state(path: str, state: dict[str, Any]) -> None:
    tmp_path = path + ".tmp"
    try:
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2, sort_keys=True)
        os.replace(tmp_path, path)
    except OSError as exc:
        logger.error("Failed to save state file: %s", exc)


def already_processed(state: dict[str, Any], signal_key: str) -> bool:
    return signal_key in state.get("processed_candles", {})


def mark_processed(state: dict[str, Any], signal_key: str) -> None:
    state.setdefault("processed_candles", {})[signal_key] = True


def get_active_signal(state: dict[str, Any], symbol: str) -> dict[str, Any] | None:
    return state.get("active_signals", {}).get(symbol)


def set_active_signal(state: dict[str, Any], symbol: str, signal: dict[str, Any]) -> None:
    state.setdefault("active_signals", {})[symbol] = signal


def clear_active_signal(state: dict[str, Any], symbol: str) -> None:
    state.get("active_signals", {}).pop(symbol, None)
