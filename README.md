# XAUUSDm Algorithmic Trading Bot

This repository contains a rules-based algorithmic trading bot tailored specifically for Gold (`XAUUSDm`) on MetaTrader 5 via Exness.

The bot automates a robust discretionary strategy based on multi-timeframe Support & Resistance (S/R), Daily/Weekly structural trend alignment, liquidity tracking, and highly defensive news-event handling.

---

## 📖 Table of Contents
1. [Core Strategy & Rules](#core-strategy--rules)
2. [Configuration Settings](#configuration-settings)
3. [Architecture Overview](#architecture-overview)
4. [Prerequisites](#prerequisites)
5. [Installation & Setup](#installation--setup)
6. [Usage Guide](#usage-guide)
7. [Risk & Disclaimers](#risk--disclaimers)

---

## 🧠 Core Strategy & Rules

The system is designed to trigger trades only when an intricate set of confluence factors perfectly align. It is built to prioritize capital preservation and strictly manage risk around volatility.

### 1. Multi-Timeframe Support & Resistance (S/R)
The bot detects swings across a 5-tier hierarchy, explicitly sizing its detection windows and tolerance thresholds based on the timeframe:
- **Yearly**: Major structural zones (derived from Monthly data).
- **Monthly (MN1)**: Major zones defining broad directional context.
- **Weekly (W1)**: Primary actionable zones.
- **Daily (D1)**: Entry-precision refinements.
- **Intraday (M5/M15)**: Minor consolidations for scalp relevance.

Zones require ≥2 touches to be confirmed. The system assigns a "confluence score" when lower-timeframe clusters align tightly inside higher-timeframe boundaries.

### 2. Market Trend State Machine
The bot identifies structure (Higher-Highs/Higher-Lows vs. Lower-Highs/Lower-Lows) on **Daily** and **Weekly** charts. 
It tracks 3 strict states:
1. `active`: Trend is intact and tradable.
2. `terminated`: Price closes against the most recent swing structure (invalidating the bias).
3. `reversal_confirmed`: After termination, a genuine new structural sequence begins.

*Trades are only taken if the Daily and Weekly trends perfectly align with the S/R reaction.*

### 3. Entry Confirmation Layer
All entries execute on the **M5** timeframe.
- When all entry conditions are met on an M5 candle close, the bot flags it as a *candidate signal*.
- The bot waits for the **next** M5 candle to close. If the conditions still hold, the trade executes. This 1-candle delay prevents false breakouts and wick-spam from triggering trades.

### 4. Dynamic Stops and Targets
- **Stop-Loss (SL)**: Structural. Anchored precisely to the high/low of the M5 candle immediately preceding the entry, plus a slight buffer.
- **Take-Profit (TP)**: Targets the next valid S/R zone. Intraday entries will actively search for the next Daily or Weekly zone as the target, only falling back to a closer Intraday zone if it sits directly in the way.

### 5. Defensive News Handling
Gold is highly sensitive to macroeconomic news (NFP, CPI, FOMC). The bot uses a 3-layer defense:
1. **Pre-News Closure**: 10 minutes before a scheduled high-impact event, the bot market-closes all open positions to remove exposure. (Includes a retry and SL-breakeven fallback mechanism).
2. **Spread Normalization Gate**: Post-news, the bot actively tracks the live `XAUUSDm` spread against a rolling normal baseline. It completely locks out new trades until the spread collapses back to normal (with a hard 60s floor and 30m ceiling).
3. **News-Confirmed Entries**: If a signal occurs during a news event, the bot cross-references a macroeconomic calendar feed. The fundamental surprise (actual vs forecast) must directionally agree with the technical signal.

---

## ⚙️ Configuration Settings

All parameters are exposed in `config/settings.py`. Key settings include:

### Risk Management
- `MAX_CONCURRENT_POSITIONS = 1`: Single-instrument focus.
- `DAILY_LOSS_LIMIT_USD = 50.0`: Hard circuit breaker on daily PnL.
- `SL_BUFFER_POINTS = 5.0`: Pips added/subtracted to the structural SL.

### S/R Tuning
```python
SR_TIER_SETTINGS = {
    "Yearly":   {"window": 24, "tolerance": 0.0030},
    "MN1":      {"window": 12, "tolerance": 0.0025},
    "W1":       {"window": 8,  "tolerance": 0.0020},
    "D1":       {"window": 5,  "tolerance": 0.0015},
    "Intraday": {"window": 20, "tolerance": 0.0005}
}
```

### News & Backtesting
- `NEWS_PRECLOSE_MINUTES = 10`: Minutes before an event to go flat.
- `SPREAD_NORMALIZATION_FACTOR = 1.3`: Max allowed spread multiple for post-news re-entry.
- `BACKTEST_SPREAD_POINTS = 30`: Simulates realistic spread directly in the historical backtester.

---

## 🏗️ Architecture Overview

- **`config/`**: Centralized parameters and blackout schedules.
- **`data/`**: Scripts for fetching/caching MT5 OHLC history and mocked news feeds.
- **`strategy/`**: The brain of the bot (`sr_levels.py`, `trend.py`, `signal_engine.py`).
- **`risk/`**: Validates positions against daily limits, max limits, and active news blackouts.
- **`execution/`**: Wrappers for sending and modifying orders to MT5.
- **`backtest/`**: Simulation framework leveraging `backtesting.py` to evaluate the strategy historically.
- **`live/`**: The main live execution loop (`run_bot.py`) and robust file logger.

---

## 🛠️ Prerequisites

1. **Windows OS or Windows VPS**: Required for the MetaTrader 5 terminal.
2. **Python 3.10+**: Ensure Python is added to your system PATH.
3. **MetaTrader 5 Terminal**: Installed and logged into an Exness Demo or Real account.
4. **Symbol Availability**: `XAUUSDm` must be visible in your MT5 Market Watch.

---

## 🚀 Installation & Setup

1. **Clone the Repository**
   ```bash
   git clone https://github.com/J-odion/s-r-bot.git
   cd s-r-bot
   ```

2. **Set Up the Virtual Environment**
   ```bash
   python -m venv venv
   venv\Scripts\activate
   ```

3. **Install Dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure Credentials**
   - Copy the `.env.example` file and rename it to `.env`.
   - Open `.env` and fill in your Exness credentials:
     ```env
     MT5_LOGIN=your_account_number
     MT5_PASSWORD=your_password
     MT5_SERVER=Exness-MT5Trial6  # IMPORTANT: Match your exact server name
     ```

---

## 💻 Usage Guide

### 1. Fetching Data
Before running backtests or testing live evaluation, build your local data cache. *Ensure your MT5 terminal is open and logged in.*
```bash
python data/fetch.py --years 3
```
This pulls history for MN1, W1, D1, H4, H1, M15, and M5 into the `data/cache/` directory.

### 2. Running a Backtest
Simulate the strategy historically to verify rules and analyze performance.
```bash
# Run a standard backtest
python backtest/engine.py

# Run a backtest leaving the last 6 months out of sample
python backtest/engine.py --holdout-months 6
```
Results and plots are saved to `backtest/results/`.

### 3. Running Live on Demo (Paper Trading)
Kick off the live polling loop. The bot will automatically hook into MT5, monitor the spread, calculate the S/R hierarchies, and execute trades.
```bash
python live/run_bot.py
```
Monitor the bot's decisions in real-time in the `live/logs/` directory.

### 4. Running Tests
If you wish to verify the core logic engines (Trend states, TP targeting, News window gating):
```bash
python -m pytest tests/test_strategy.py
```

---

## ⚠️ Risk & Disclaimers

**This bot is an execution tool for a discretionary strategy, not a guaranteed-profit machine.**
- Always run this on a **Demo Account** for a minimum of 4–8 weeks before considering live capital.
- The default configurations and thresholds (e.g. S/R tolerances, ADX periods) are starting points and require tuning against historical data.
- Slippage and spread widening during macroeconomic events on Gold can be extreme. The bot features defensive handling, but you must verify its execution speed against your broker's latency.
