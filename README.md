# Gold-Signal-Bot

A Telegram signal bot for Forex, Gold (XAUUSD) and Bitcoin (BTCUSD) that
watches the 5-minute (M5) chart for RSI + MACD crossover setups and
notifies you on Telegram. Runs entirely on GitHub Actions — no server,
VPS or always-on computer required.

## ⚠️ Disclaimer

This is a **technical signal notifier only**. It does not place trades,
does not guarantee profitability, and TP1 is not a guaranteed outcome —
it is simply "RSI has returned to 50." Always use your own risk
management. Nothing here is financial advice.

## Strategy

**Timeframe:** M5 (5-minute candles), confirmed/closed candles only.

**BUY signal** — both conditions must be true on the same confirmed candle:
- RSI(14) is between 10 and 15
- MACD(10, 22, 4) crosses **bullish**: previous MACD ≤ previous Signal,
  and current MACD > current Signal

**SELL signal** — both conditions must be true on the same confirmed candle:
- RSI(14) is between 85 and 90
- MACD(10, 22, 4) crosses **bearish**: previous MACD ≥ previous Signal,
  and current MACD < current Signal

**TP1** is reached when RSI subsequently returns to 50 (from either
direction). This is an RSI-based exit condition, not a fixed price
target.

## Supported markets

7 forex majors, 20 forex cross pairs, XAUUSD (Gold) and BTCUSD — see
`config.py` → `SYMBOLS` for the full list and their Yahoo Finance ticker
mapping.

## Project structure

```
Gold-Signal-Bot/
├── bot.py                      # main entry point
├── config.py                   # all tunable settings
├── indicators.py                # RSI / MACD math
├── market_data.py               # Yahoo Finance data fetching + retries
├── telegram_service.py          # Telegram Bot API wrapper
├── telegram_test.py             # standalone connectivity check (CI step)
├── signal_engine.py             # per-symbol signal + TP1 logic
├── state_manager.py             # state.json read/write helpers
├── state.json                   # persisted "already sent" signal keys
├── requirements.txt
├── .gitignore
├── README.md
└── .github/workflows/main.yml   # scheduled + manual GitHub Action
```

## Telegram setup

1. Message **@BotFather** on Telegram, send `/newbot`, follow the
   prompts. You'll receive a bot token like `123456789:AAExampleToken`.
2. Start a chat with your new bot (send it any message).
3. Find your chat ID — the easiest way is to message
   **@userinfobot** and copy the numeric ID it replies with.

## GitHub Secrets setup

In your repository:

1. Go to **Settings → Secrets and variables → Actions**.
2. Click **New repository secret**, create:
   - Name: `TELEGRAM_BOT_TOKEN` — Value: your BotFather token
   - Name: `TELEGRAM_CHAT_ID` — Value: your chat ID
3. Never commit these values into any file. The workflow reads them via
   `${{ secrets.TELEGRAM_BOT_TOKEN }}` / `${{ secrets.TELEGRAM_CHAT_ID }}`
   only.

If a token is ever accidentally exposed (posted publicly, committed to
git, pasted in a chat), go back to @BotFather, use `/revoke`, and
generate a new token before updating the secret.

## Running it

### Manual run
1. Go to the **Actions** tab of your repository.
2. Select **RSI MACD Signal Bot** in the left sidebar.
3. Click **Run workflow**.
4. Open the run, then the `run-bot` job:
   - **Test Telegram** step should succeed and your bot should send
     "✅ Telegram connection test successful."
   - **Run signal bot** step should succeed and your bot should send
     "🤖 Gold Signal Bot Started".

### Scheduled run
The workflow also runs automatically every 5 minutes
(`cron: "*/5 * * * *"`). GitHub does not guarantee the exact minute a
scheduled workflow fires — under load it can be a few minutes late. The
bot's confirmed-candle logic and duplicate-signal protection are
designed to work correctly even if a run is delayed.

## How duplicate protection works

Every signal is keyed as `SYMBOL_DIRECTION_CANDLE-TIMESTAMP`
(e.g. `XAUUSD_BUY_2026-09-24T14:30:00`). Once that key has been sent, it
is recorded in `state.json` and will never be sent again, even if the
same candle is re-processed on a later run. The same protection applies
to TP1 notifications (keyed with a `_TP1` suffix).

`state.json` is committed back to the repository at the end of every
run by the **Persist state file** workflow step, so the bot remembers
what it has already sent across separate GitHub Actions jobs.

## Inspecting logs

Open **Actions → (a run) → run-bot**, then expand the **Run signal bot**
step. You'll see structured log lines like:

```
INFO - Checking XAUUSD
INFO - XAUUSD RSI=12.8 MACD bullish crossover -> BUY signal generated
INFO - Telegram message sent successfully.
```

Errors are clearly marked with `ERROR` or `WARNING`, and a failed
Telegram delivery always prints the HTTP status and Telegram's response
body (never the token).

## Limitations of Yahoo Finance M5 data

- Yahoo Finance only retains intraday (5-minute) data for a limited
  rolling window (a few days), which is why `CANDLE_HISTORY_PERIOD` in
  `config.py` is set to `"5d"`.
- Yahoo occasionally returns gaps, especially around weekends/market
  closures for forex pairs, or temporary outages. `market_data.py`
  retries failed requests and skips a symbol for that run rather than
  crashing if data can't be retrieved.
- If Yahoo Finance becomes unreliable for your use case, only
  `market_data.py` needs to be replaced — every other module works with
  the same `fetch_candles()` return type.

## Telegram commands

This bot is **signal-only**. It does not use Telegram long-polling
(`getUpdates`), because GitHub Actions runs are short-lived by design —
there's no always-on process to listen for incoming commands. `/start`,
`/help`, `/status` are **not implemented**; adding them would require a
long-running host (e.g. a VPS) instead of GitHub Actions.
