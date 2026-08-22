# XAUUSDm Bot Configuration

# Symbol and Timeframes
SYMBOL = "XAUUSDm"
ENTRY_TIMEFRAME = "M5"
TREND_TIMEFRAMES = ["D1", "W1"]
SR_TIMEFRAMES = ["M5", "M15", "H1", "H4", "D1", "W1", "MN1"] # Extended for more granular checking

# Support & Resistance (S/R) Settings
# Dictionary mapping tier to {"window": int, "tolerance": float}
SR_TIER_SETTINGS = {
    "Yearly":   {"window": 24, "tolerance": 0.0030}, # Derived from MN1, wide window
    "MN1":      {"window": 12, "tolerance": 0.0025},
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
NEWS_BLACKOUT_WINDOWS = [
    # {"day": 4, "start": "12:00", "end": "15:00"}, # Example Friday blackout
]
NEWS_PRECLOSE_MINUTES = 10
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
