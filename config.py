"""Central configuration for Gold-Signal-Bot.

All tunable values live here so nothing is duplicated across modules.
"""

# --- Timeframe & data ---
TIMEFRAME = "5m"
CANDLE_HISTORY_PERIOD = "5d"   # how much history to pull from Yahoo Finance
MIN_CANDLES_REQUIRED = 100     # minimum candles needed before trusting indicators

# --- RSI settings ---
RSI_PERIOD = 14
RSI_BUY_MIN = 10
RSI_BUY_MAX = 15
RSI_SELL_MIN = 85
RSI_SELL_MAX = 90

# --- MACD settings ---
MACD_FAST = 10
MACD_SLOW = 22
MACD_SIGNAL = 4

# --- Take profit ---
TP1_RSI = 50

# --- Runtime behaviour (must fit inside the GitHub Actions job timeout) ---
CHECK_INTERVAL_SECONDS = 60
RUN_SECONDS = 240

# --- State persistence ---
STATE_FILE = "state.json"

# --- Internal symbol -> Yahoo Finance symbol mapping ---
SYMBOLS: dict[str, str] = {
    # Forex majors
    "EURUSD": "EURUSD=X",
    "GBPUSD": "GBPUSD=X",
    "USDJPY": "JPY=X",
    "USDCHF": "CHF=X",
    "USDCAD": "CAD=X",
    "AUDUSD": "AUDUSD=X",
    "NZDUSD": "NZDUSD=X",
    # Forex crosses
    "EURGBP": "EURGBP=X",
    "EURJPY": "EURJPY=X",
    "EURAUD": "EURAUD=X",
    "EURCAD": "EURCAD=X",
    "EURCHF": "EURCHF=X",
    "EURNZD": "EURNZD=X",
    "GBPJPY": "GBPJPY=X",
    "GBPAUD": "GBPAUD=X",
    "GBPCAD": "GBPCAD=X",
    "GBPCHF": "GBPCHF=X",
    "GBPNZD": "GBPNZD=X",
    "AUDJPY": "AUDJPY=X",
    "AUDCAD": "AUDCAD=X",
    "AUDCHF": "AUDCHF=X",
    "AUDNZD": "AUDNZD=X",
    "CADJPY": "CADJPY=X",
    "CADCHF": "CADCHF=X",
    "CHFJPY": "CHFJPY=X",
    "NZDJPY": "NZDJPY=X",
    "NZDCAD": "NZDCAD=X",
    # Metals & crypto
    "XAUUSD": "GC=F",
    "BTCUSD": "BTC-USD",
}

# Pairs that should be displayed with 3 decimal places instead of 5.
JPY_PAIRS = {"USDJPY", "EURJPY", "GBPJPY", "AUDJPY", "CADJPY", "CHFJPY", "NZDJPY"}
