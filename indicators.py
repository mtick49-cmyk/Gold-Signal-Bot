"""Technical indicator calculations: RSI and MACD.

Both functions operate on a pandas Series of closing prices and return
pandas Series aligned to the same index.
"""
from __future__ import annotations

import pandas as pd


def calculate_rsi(close: pd.Series, period: int) -> pd.Series:
    """Relative Strength Index using Wilder's smoothing (EMA-based)."""
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = gain.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()

    # Avoid division by zero when there have been no losses at all.
    rs = avg_gain / avg_loss.replace(0, 1e-10)
    rsi = 100 - (100 / (1 + rs))
    return rsi


def calculate_macd(
    close: pd.Series, fast: int, slow: int, signal: int
) -> tuple[pd.Series, pd.Series, pd.Series]:
    """Returns (macd_line, signal_line, histogram)."""
    ema_fast = close.ewm(span=fast, adjust=False).mean()
    ema_slow = close.ewm(span=slow, adjust=False).mean()

    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    histogram = macd_line - signal_line

    return macd_line, signal_line, histogram
