import os
import time
import requests
import pandas as pd

# =========================
# TELEGRAM
# =========================
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# =========================
# SETTINGS
# =========================
SYMBOL = "GC=F"          # XAUUSD
CHECK_SECONDS = 60

RSI_PERIOD = 14

MACD_FAST = 10
MACD_SLOW = 22
MACD_SIGNAL = 4

# 5$ balance
ACCOUNT_BALANCE = 5.0
RISK_PERCENT = 1.0

TIMEFRAMES = {
    "M5": "5m",
    "M15": "15m",
    "M30": "30m",
    "H1": "60m",
    "H4": "1h",
}

# =========================
# TELEGRAM SEND
# =========================
def send_message(text):
    if not TOKEN or not CHAT_ID:
        print("Telegram secrets yok!")
        return False

    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"

    try:
        response = requests.post(
            url,
            data={
                "chat_id": CHAT_ID,
                "text": text
            },
            timeout=20
        )

        print("Telegram:", response.status_code, response.text)

        return response.ok

    except Exception as e:
        print("Telegram error:", e)
        return False


# =========================
# GET MARKET DATA
# =========================
def get_data(interval):
    url = (
        "https://query1.finance.yahoo.com/v8/finance/chart/"
        f"{SYMBOL}?interval={interval}&range=10d"
    )

    response = requests.get(url, timeout=20)
    response.raise_for_status()

    data = response.json()["chart"]["result"][0]

    timestamps = data["timestamp"]
    quote = data["indicators"]["quote"][0]

    df = pd.DataFrame({
        "time": pd.to_datetime(timestamps, unit="s"),
        "open": quote["open"],
        "high": quote["high"],
        "low": quote["low"],
        "close": quote["close"],
    })

    df = df.dropna().reset_index(drop=True)

    return df


# =========================
# RSI
# =========================
def calculate_rsi(series, period=14):
    delta = series.diff()

    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = gain.ewm(
        alpha=1 / period,
        min_periods=period,
        adjust=False
    ).mean()

    avg_loss = loss.ewm(
        alpha=1 / period,
        min_periods=period,
        adjust=False
    ).mean()

    rs = avg_gain / avg_loss.replace(0, 1e-10)

    return 100 - (100 / (1 + rs))


# =========================
# MACD
# =========================
def calculate_macd(df):
    close = df["close"]

    fast = close.ewm(
        span=MACD_FAST,
        adjust=False
    ).mean()

    slow = close.ewm(
        span=MACD_SLOW,
        adjust=False
    ).mean()

    macd = fast - slow

    signal = macd.ewm(
        span=MACD_SIGNAL,
        adjust=False
    ).mean()

    df["macd"] = macd
    df["signal"] = signal

    return df


# =========================
# ATR
# =========================
def calculate_atr(df, period=14):
    high = df["high"]
    low = df["low"]
    close = df["close"]

    previous_close = close.shift(1)

    tr1 = high - low
    tr2 = (high - previous_close).abs()
    tr3 = (low - previous_close).abs()

    tr = pd.concat(
        [tr1, tr2, tr3],
        axis=1
    ).max(axis=1)

    return tr.rolling(period).mean()


# =========================
# MACD TOUCH
# =========================
def macd_touch(df):
    if len(df) < 3:
        return None

    current = df.iloc[-1]
    previous = df.iloc[-2]

    current_diff = current["macd"] - current["signal"]
    previous_diff = previous["macd"] - previous["signal"]

    atr = calculate_atr(df).iloc[-1]

    if pd.isna(atr) or atr <= 0:
        return None

    # MACD lines crossing each other
    bullish_cross = (
        previous_diff <= 0 and
        current_diff >= 0
    )

    bearish_cross = (
        previous_diff >= 0 and
        current_diff <= 0
    )

    # "Touch" tolerance
    tolerance = atr * 0.02

    touching = abs(current_diff) <= tolerance

    if bullish_cross or touching and current_diff >= 0:
        return "BUY"

    if bearish_cross or touching and current_diff <= 0:
        return "SELL"

    return None


# =========================
# M5 SIGNAL
# =========================
def get_m5_signal():
    df = get_data("5m")

    df["rsi"] = calculate_rsi(
        df["close"],
        RSI_PERIOD
    )

    df = calculate_macd(df)

    rsi = float(df["rsi"].iloc[-1])
    price = float(df["close"].iloc[-1])

    macd_signal = macd_touch(df)

    if 10 <= rsi <= 15 and macd_signal == "BUY":
        return "BUY", price, rsi, df

    if 85 <= rsi <= 90 and macd_signal == "SELL":
        return "SELL", price, rsi, df

    return None, price, rsi, df


# =========================
# TIMEFRAME DIRECTION
# =========================
def timeframe_direction(interval):
    df = get_data(interval)

    df["rsi"] = calculate_rsi(
        df["close"],
        RSI_PERIOD
    )

    df = calculate_macd(df)

    rsi = float(df["rsi"].iloc[-1])

    macd = float(df["macd"].iloc[-1])
    signal = float(df["signal"].iloc[-1])

    if macd > signal and rsi >= 50:
        return "BUY", rsi

    if macd < signal and rsi <= 50:
        return "SELL", rsi

    return "NEUTRAL", rsi


# =========================
# CONFIRMATIONS
# =========================
def get_confirmations(direction):
    confirmations = {}

    for name in ["M15", "M30", "H1", "H4"]:
        try:
            tf_direction, rsi = timeframe_direction(
                TIMEFRAMES[name]
            )

            confirmations[name] = {
                "direction": tf_direction,
                "rsi": rsi
            }

        except Exception as e:
            print(name, "error:", e)

            confirmations[name] = {
                "direction": "NEUTRAL",
                "rsi": 0
            }

    return confirmations


# =========================
# SL
# =========================
def calculate_sl(entry, direction, df):
    atr = calculate_atr(df).iloc[-1]

    if pd.isna(atr) or atr <= 0:
        atr = entry * 0.001

    # 5$ balance + 1% risk
    risk_money = ACCOUNT_BALANCE * (
        RISK_PERCENT / 100
    )

    # Conservative SL distance
    sl_distance = atr * 1.5

    if direction == "BUY":
        sl = entry - sl_distance
    else:
        sl = entry + sl_distance

    return sl, risk_money


# =========================
# SIGNAL MESSAGE
# =========================
def build_signal(
    direction,
    entry,
    m5_rsi,
    confirmations,
    sl
):
    aligned = 0

    for name in ["M15", "M30", "H1", "H4"]:
        if confirmations[name]["direction"] == direction:
            aligned += 1

    vip = aligned >= 3

    title = "🔥 VIP SIGNAL 🔥" if vip else "📊 M5 SIGNAL"

    text = (
        f"{title}\n\n"
        f"XAUUSD {direction}\n"
        f"Entry: {entry:.2f}\n"
        f"Timeframe: M5\n"
        f"RSI M5: {m5_rsi:.2f}\n"
        f"MACD: TOUCH\n\n"
        f"Confirmation:\n"
    )

    for name in ["M15", "M30", "H1", "H4"]:
        tf = confirmations[name]

        mark = "✅" if tf["direction"] == direction else "❌"

        text += (
            f"{mark} {name}: "
            f"{tf['direction']} "
            f"(RSI {tf['rsi']:.1f})\n"
        )

    text += (
        f"\nSL: {sl:.2f}\n"
        f"TP1: H1/H4 RSI → 50\n"
        f"TP2: Next strong signal\n"
        f"\nBalance model: $5"
    )

    return text


# =========================
# MAIN
# =========================
def main():

    send_message(
        "🤖 XAUUSD RSI + MACD Multi-Timeframe Bot started\n"
        "M5 Signal + M15/M30/H1/H4 Confirmation"
    )

    last_signal = None

    while True:

        try:

            direction, entry, rsi, m5_df = get_m5_signal()

            print(
                "M5:",
                direction,
                "Entry:",
                entry,
                "RSI:",
                rsi
            )

            if direction:

                signal_key = (
                    direction,
                    round(entry, 2),
                    m5_df["time"].iloc[-1]
                )

                if signal_key != last_signal:

                    confirmations = get_confirmations(
                        direction
                    )

                    sl, risk_money = calculate_sl(
                        entry,
                        direction,
                        m5_df
                    )

                    message = build_signal(
                        direction,
                        entry,
                        rsi,
                        confirmations,
                        sl
                    )

                    send_message(message)

                    last_signal = signal_key

        except Exception as e:

            print(
                "MAIN ERROR:",
                repr(e)
            )

        time.sleep(CHECK_SECONDS)


if __name__ == "__main__":
    main()
