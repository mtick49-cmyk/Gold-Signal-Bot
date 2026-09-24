"""Core signal generation logic: RSI + MACD crossover strategy.

For each symbol this module:
  1. Downloads M5 candles.
  2. Calculates RSI and MACD.
  3. Looks only at fully confirmed (closed) candles.
  4. Checks the exact BUY / SELL conditions from the spec.
  5. Sends a Telegram signal if a new, not-yet-sent signal exists.
  6. Tracks the active signal and watches for the RSI-50 TP1 condition.
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

import pandas as pd

import config
import state_manager
from indicators import calculate_macd, calculate_rsi
from market_data import fetch_candles
from telegram_service import send_message

logger = logging.getLogger("gold_signal_bot.signal_engine")


def format_price(symbol: str, price: float) -> str:
    """Format a price with the correct number of decimals for its market."""
    if symbol in ("XAUUSD", "BTCUSD"):
        return f"{price:.2f}"
    if symbol in config.JPY_PAIRS:
        return f"{price:.3f}"
    return f"{price:.5f}"


def _build_signal_message(symbol: str, direction: str, entry: float, rsi: float, ts: datetime) -> str:
    emoji = "🟢" if direction == "BUY" else "🔴"
    macd_desc = "Bullish Cross" if direction == "BUY" else "Bearish Cross"
    condition = "RSI reaches 50+" if direction == "BUY" else "RSI reaches 50-"
    return (
        f"{emoji} {direction} SIGNAL\n\n"
        f"Symbol: {symbol}\n"
        f"Timeframe: M5\n"
        f"Entry: {format_price(symbol, entry)}\n"
        f"RSI: {rsi:.1f}\n"
        f"MACD: {macd_desc}\n\n"
        f"🎯 TP1: RSI 50\n"
        f"🛑 Condition: {condition}\n\n"
        f"Time: {ts.strftime('%Y-%m-%d %H:%M')} UTC"
    )


def _build_tp1_message(symbol: str, direction: str, entry: float, ts: datetime) -> str:
    return (
        f"✅ TP1 REACHED\n\n"
        f"Symbol: {symbol}\n"
        f"Direction: {direction}\n"
        f"Timeframe: M5\n\n"
        f"RSI reached 50.\n\n"
        f"Original Entry: {format_price(symbol, entry)}\n\n"
        f"Time: {ts.strftime('%Y-%m-%d %H:%M')} UTC"
    )


def process_symbol(
    symbol: str,
    yahoo_symbol: str,
    token: str,
    chat_id: str,
    state: dict[str, Any],
) -> None:
    """Check one symbol for new signals and TP1 completion. Never raises."""
    logger.info("Checking %s", symbol)

    df = fetch_candles(yahoo_symbol, interval=config.TIMEFRAME, period=config.CANDLE_HISTORY_PERIOD)
    if df is None or df.empty:
        logger.warning("No valid data for %s", symbol)
        return

    if len(df) < config.MIN_CANDLES_REQUIRED:
        logger.warning(
            "Insufficient candles for %s: got %d, need >= %d",
            symbol, len(df), config.MIN_CANDLES_REQUIRED,
        )
        return

    close = df["Close"]
    rsi = calculate_rsi(close, config.RSI_PERIOD)
    macd_line, signal_line, _ = calculate_macd(
        close, config.MACD_FAST, config.MACD_SLOW, config.MACD_SIGNAL
    )

    if len(df) < 3:
        logger.warning("Not enough confirmed candles for %s", symbol)
        return

    # The very last row from Yahoo Finance can be a still-forming candle.
    # We treat index -2 as the latest *confirmed* candle, and -3 as the
    # confirmed candle before it, so the crossover comparison never uses
    # an unfinished bar.
    current_idx = -2
    previous_idx = -3

    try:
        current_close = float(close.iloc[current_idx])
        current_rsi = float(rsi.iloc[current_idx])
        current_macd = float(macd_line.iloc[current_idx])
        current_signal = float(signal_line.iloc[current_idx])
        previous_macd = float(macd_line.iloc[previous_idx])
        previous_signal = float(signal_line.iloc[previous_idx])
        candle_time = df.index[current_idx]
    except (IndexError, ValueError) as exc:
        logger.warning("Could not extract indicator values for %s: %s", symbol, exc)
        return

    values = [current_rsi, current_macd, current_signal, previous_macd, previous_signal]
    if any(pd.isna(v) for v in values):
        logger.warning("NaN indicator values for %s, skipping this run.", symbol)
        return

    candle_ts = pd.Timestamp(candle_time)
    candle_ts = candle_ts.tz_localize("UTC") if candle_ts.tzinfo is None else candle_ts.tz_convert("UTC")
    candle_iso = candle_ts.strftime("%Y-%m-%dT%H:%M:%S")

    buy_macd_cross = previous_macd <= previous_signal and current_macd > current_signal
    sell_macd_cross = previous_macd >= previous_signal and current_macd < current_signal

    is_buy = buy_macd_cross and config.RSI_BUY_MIN <= current_rsi <= config.RSI_BUY_MAX
    is_sell = sell_macd_cross and config.RSI_SELL_MIN <= current_rsi <= config.RSI_SELL_MAX

    direction = "BUY" if is_buy else ("SELL" if is_sell else None)

    if direction:
        signal_key = f"{symbol}_{direction}_{candle_iso}"
        if state_manager.already_processed(state, signal_key):
            logger.info("Signal %s already sent, skipping duplicate.", signal_key)
        else:
            logger.info(
                "%s RSI=%.1f MACD %s crossover -> %s signal generated",
                symbol, current_rsi, "bullish" if is_buy else "bearish", direction,
            )
            message = _build_signal_message(symbol, direction, current_close, current_rsi, candle_ts)
            if send_message(token, chat_id, message):
                state_manager.mark_processed(state, signal_key)
                state_manager.set_active_signal(
                    state,
                    symbol,
                    {
                        "direction": direction,
                        "entry_price": current_close,
                        "signal_timestamp": candle_iso,
                        "tp1_reached": False,
                    },
                )
            else:
                logger.error("Failed to send %s signal for %s, will retry next run.", direction, symbol)

    _check_tp1(symbol, current_rsi, candle_ts, token, chat_id, state)


def _check_tp1(
    symbol: str,
    current_rsi: float,
    candle_ts: pd.Timestamp,
    token: str,
    chat_id: str,
    state: dict[str, Any],
) -> None:
    active = state_manager.get_active_signal(state, symbol)
    if not active or active.get("tp1_reached", False):
        return

    active_direction = active["direction"]
    tp1_hit = (
        (active_direction == "BUY" and current_rsi >= config.TP1_RSI)
        or (active_direction == "SELL" and current_rsi <= config.TP1_RSI)
    )
    if not tp1_hit:
        return

    tp1_key = f"{symbol}_{active_direction}_{active['signal_timestamp']}_TP1"
    if state_manager.already_processed(state, tp1_key):
        return

    message = _build_tp1_message(symbol, active_direction, active["entry_price"], candle_ts)
    if send_message(token, chat_id, message):
        state_manager.mark_processed(state, tp1_key)
        state_manager.clear_active_signal(state, symbol)
    else:
        logger.error("Failed to send TP1 notification for %s, will retry next run.", symbol)
