"""Market data retrieval via Yahoo Finance (through the yfinance library).

This module is intentionally the only place that knows how candle data is
fetched. If Yahoo Finance ever needs to be swapped for another provider,
only fetch_candles() needs to change -- every caller just gets a
DataFrame back (or None on failure).
"""
from __future__ import annotations

import logging
import time

import pandas as pd
import yfinance as yf

logger = logging.getLogger("gold_signal_bot.market_data")

MAX_RETRIES = 3
RETRY_DELAY_SECONDS = 5

REQUIRED_COLUMNS = {"Open", "High", "Low", "Close"}


def fetch_candles(yahoo_symbol: str, interval: str, period: str) -> pd.DataFrame | None:
    """Fetch OHLC candles for a symbol.

    Returns a cleaned DataFrame indexed by timestamp, or None if the data
    could not be retrieved after retrying.
    """
    last_error: str | None = None

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            data = yf.download(
                tickers=yahoo_symbol,
                interval=interval,
                period=period,
                progress=False,
                auto_adjust=False,
                threads=False,
            )
        except Exception as exc:  # network errors, timeouts, parsing issues, etc.
            last_error = str(exc)
            logger.warning(
                "Error fetching data for %s (attempt %d/%d): %s",
                yahoo_symbol, attempt, MAX_RETRIES, exc,
            )
            time.sleep(RETRY_DELAY_SECONDS)
            continue

        if data is None or data.empty:
            last_error = "empty dataframe"
            logger.warning(
                "No data returned for %s (attempt %d/%d)",
                yahoo_symbol, attempt, MAX_RETRIES,
            )
            time.sleep(RETRY_DELAY_SECONDS)
            continue

        # yfinance sometimes returns MultiIndex columns (ticker, field).
        if isinstance(data.columns, pd.MultiIndex):
            data.columns = [c[0] for c in data.columns]

        if not REQUIRED_COLUMNS.issubset(set(data.columns)):
            last_error = f"missing columns, got {list(data.columns)}"
            logger.warning(
                "Missing required columns for %s (attempt %d/%d): got %s",
                yahoo_symbol, attempt, MAX_RETRIES, list(data.columns),
            )
            time.sleep(RETRY_DELAY_SECONDS)
            continue

        data = data.dropna(subset=["Close"])
        if data.empty:
            last_error = "all rows had NaN close"
            time.sleep(RETRY_DELAY_SECONDS)
            continue

        return data

    logger.error(
        "Failed to fetch data for %s after %d attempts: %s",
        yahoo_symbol, MAX_RETRIES, last_error,
    )
    return None
