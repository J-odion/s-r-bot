# XAUUSDm Bot Configuration

import os
from dotenv import load_dotenv
load_dotenv()

# Symbol and Timeframes
SYMBOL = "XAUUSD"
ENTRY_TIMEFRAME = "M5"
TREND_TIMEFRAMES = ["D1", "W1"]
SR_TIMEFRAMES = ["M5", "M15", "H1", "H4", "D1", "W1", "MN1"] # Extended for more granular checking

# Support & Resistance (S/R) Settings
# Dictionary mapping tier to {"window": int, "tolerance": float}
# Note on windows (Item 5): detect_swing_points uses a centered rolling window of size (2*window + 1).
# Therefore, a "window" of 12 on MN1 equals 12 months before + 12 months after = 25 months total lookback.
# Yearly uses a window of 24 on MN1 (48+ months lookback) to capture multi-year extremes.
SR_TIER_SETTINGS = {
    "Yearly":   {"window": 24, "tolerance": 0.0030}, # ~48-month lookback on MN1 data
    "MN1":      {"window": 12, "tolerance": 0.0025}, # ~25-month lookback on MN1 data
    "W1":       {"window": 8,  "tolerance": 0.0020},
    "D1":       {"window": 5,  "tolerance": 0.0015},
    "Intraday": {"window": 20, "tolerance": 0.0005}  # M5/M15/H1/H4 mapped to this
}

# Trend Settings
ADX_THRESHOLD = 25
ADX_PERIOD = 14

# Liquidity Gaps Settings
GAP_THRESHOLD_POINTS = 20  # Default to 20 points, to be tuned
FVG_ENABLED = False        # Disabled by default until validated

# Liquidity Sweeps Settings
SWEEP_THRESHOLD_POINTS = 30    # Default to 30 points, to be tuned
SWEEP_REVERSAL_CANDLES = 3     # Max candles to close back inside

# Risk Management
MAX_CONCURRENT_POSITIONS = 1
DAILY_LOSS_LIMIT_USD = 50.0  # Example limit, set appropriately
SL_BUFFER_POINTS = 5.0       # Buffer beyond structural SL point

# Backtesting Realism
BACKTEST_SPREAD_POINTS = 30  # e.g., 30 points = 3.0 pips

# News Handling Settings
NEWS_REACTION_ENABLED = False # Item 1 Option B: Disable news-confirmed entries until real API is connected
NEWS_BLACKOUT_WINDOWS = [
    # {"day": 4, "start": "12:00", "end": "15:00"}, # Example Friday blackout
]
NEWS_PRECLOSE_MINUTES = 10
NEWS_FALLBACK_SL_BUFFER_POINTS = 15.0 # Wider buffer for fallback breakeven SL during news
SPREAD_NORMALIZATION_FACTOR = 1.3
NEWS_MIN_WAIT_SECONDS = 60
NEWS_MAX_WAIT_MINUTES = 30
NEWS_EVENT_TYPES = ["NFP", "CPI", "FOMC"]

# Timeframes mapping to MT5 constants (to be used with mt5.TIMEFRAME_...)
# This is a helper mapping, real MT5 constants will be imported where needed.
TIMEFRAME_MAP = {
    "M5": 5,
    "M15": 15,
    "H1": 16385,
    "H4": 16388,
    "D1": 16408,
    "W1": 16411,
    "MN1": 16412
}

import os
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
