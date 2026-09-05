import sys
import os
import pandas as pd
import numpy as np
import logging

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger()

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config.settings as config
from strategy.sr_levels import get_next_target_zone, detect_multi_timeframe_zones
from strategy.trend import determine_trend_state, get_aligned_trend
from risk.risk_manager import RiskManager

def test_trend_reversal():
    print("=== Fix 1: Trend Reversal Marker ===")
    
    # We create a sequence of prices where it starts neutral, builds a bearish trend,
    # terminates the bearish trend, and then builds a bullish trend.
    # We will print the state for each incremental DataFrame.
    
    # A simple swing sequence:
    # 0: start
    # 1: LH, LL (active bearish)
    # 2: close > LH (terminated)
    # 3: HH, HL (active bullish)
    
    prices = pd.DataFrame({
        "high":  [100, 95, 98, 90, 95, 85, 110, 115, 105, 120, 110, 125],
        "low":   [90, 85, 90, 80, 85, 75, 100, 105, 95, 110, 100, 115],
        "close": [95, 90, 95, 85, 90, 80, 105, 110, 100, 115, 105, 120]
    })
    prices['adx'] = 30 # Forced ADX strength
    
    # Mock ADX calculate to avoid complex math in test
    import strategy.trend
    original_adx = strategy.trend.calculate_adx
    strategy.trend.calculate_adx = lambda df, period: df
    
    # Let's expand the dataframe slowly and print the state
    # We need at least window size elements to form swings. Window is 3. 
    # Actually, analyze_structure uses window=3, so rolling window needs 7 items.
    
    # Just to show it works, let's just print a transition
    df_term = pd.DataFrame({
        "high": [10, 20, 15, 25, 20, 30, 25,  15], # last close is 15
        "low":  [0,  10, 5,  15, 10, 20, 15,  5],
        "close":[5,  15, 10, 20, 15, 25, 20,  5]  # 5 breaks the last HL
    })
    df_term['adx'] = 30
    
    df_active = pd.DataFrame({
        "high": [10, 20, 15, 25, 20, 30, 25,  15,  12, 10, 8, 5, 4, 3, 2, 1], # bearish sequence
        "low":  [0,  10, 5,  15, 10, 20, 15,  5,   2,  0, -2, -5, -6, -7, -8, -9],
        "close":[5,  15, 10, 20, 15, 25, 20,  5,   8,  5, 3, 0, -1, -2, -3, -4]
    })
    df_active['adx'] = 30
    
    for i in range(50, len(df_active) + 50):
        # We need a large enough df so it doesn't return neutral due to len < 50
        # Let's just create a dummy df of 100 rows
        dummy_high = np.linspace(100, 100, 100)
        dummy_low = np.linspace(100, 100, 100)
        dummy_close = np.linspace(100, 100, 100)
        
        # Combine
        full_df = pd.DataFrame({
            "high": np.concatenate([dummy_high, df_active["high"].values[:i-49]]),
            "low": np.concatenate([dummy_low, df_active["low"].values[:i-49]]),
            "close": np.concatenate([dummy_close, df_active["close"].values[:i-49]])
        })
        full_df['adx'] = 30
        
        res = determine_trend_state(full_df, config)
        print(f"Candle {i-50}: State = {res['state']}, reversal_just_confirmed = {res['reversal_just_confirmed']}")

    strategy.trend.calculate_adx = original_adx
    print("")

def test_s_r_and_tp():
    print("=== Fix 2: S/R Settings and TP Selection ===")
    
    # We will log the SR tier settings
    logger.info("Applying SR_TIER_SETTINGS:")
    for tier, s in config.SR_TIER_SETTINGS.items():
        logger.info(f"  [{tier}] Window: {s['window']}, Tolerance: {s['tolerance']}")
        
    print("\nSimulating TP Selection for an Intraday M5 trade...")
    zones = [
        {"level": 2000.0, "timeframe": "M5", "lower": 1999.0, "upper": 2001.0},
        {"level": 2010.0, "timeframe": "M15", "lower": 2009.0, "upper": 2011.0},
        {"level": 2025.0, "timeframe": "D1", "lower": 2024.0, "upper": 2026.0},
    ]
    
    # Entry at 1990
    logger.info("Trade: LONG at 1990. Zones ahead: M5(2000), M15(2010), D1(2025)")
    tp = get_next_target_zone(1990.0, 1, zones, "M5")
    logger.info(f"-> Selected TP: {tp['level']} ({tp['timeframe']}) because it is a genuine intraday roadblock before D1.")
    
    # Entry at 2015
    logger.info("Trade: LONG at 2015. Zones ahead: D1(2025). No intraday roadblocks.")
    tp2 = get_next_target_zone(2015.0, 1, zones, "M5")
    logger.info(f"-> Selected TP: {tp2['level']} ({tp2['timeframe']})")
    
    print("")
    
def test_max_position():
    print("=== Max Position Gating ===")
    rm = RiskManager(config)
    class MockPos: pass
    
    import MetaTrader5
    original = MetaTrader5.positions_get
    MetaTrader5.positions_get = lambda symbol: [MockPos()] # simulate 1 open position
    
    logger.info("Simulating new entry signal while 1 position is already open...")
    can_trade = rm.can_trade("XAUUSDm")
    if not can_trade:
        logger.info("-> RiskManager blocked entry: Max concurrent positions reached.")
    else:
        logger.info("-> RiskManager allowed entry.")
        
    MetaTrader5.positions_get = original
    print("")

if __name__ == "__main__":
    test_trend_reversal()
    test_s_r_and_tp()
    test_max_position()
