import pytest
import pandas as pd
from datetime import datetime
from config import settings
from strategy.sr_levels import get_next_target_zone
from risk.news_filter import is_news_blackout
from strategy.trend import determine_trend_state
from risk.risk_manager import RiskManager

def test_take_profit_target_zone():
    zones = [
        {"level": 2400.0, "timeframe": "M5", "lower": 2399.0, "upper": 2401.0},
        {"level": 2410.0, "timeframe": "D1", "lower": 2408.0, "upper": 2412.0},
        {"level": 2380.0, "timeframe": "W1", "lower": 2378.0, "upper": 2382.0}
    ]
    
    # Long trade at 2390
    target_long = get_next_target_zone(2390.0, 1, zones)
    assert target_long["level"] == 2400.0 # M5 is closest
    
    # Long trade at 2405
    target_long2 = get_next_target_zone(2405.0, 1, zones)
    assert target_long2["level"] == 2410.0 # D1 is closest
    
    # Short trade at 2390
    target_short = get_next_target_zone(2390.0, -1, zones)
    assert target_short["level"] == 2380.0 # W1 is closest

def test_news_blackout():
    settings.NEWS_BLACKOUT_WINDOWS = [
        {"day": 4, "start": "12:00", "end": "15:00"}, # Friday 12-15
    ]
    
    # A Friday at 13:00
    friday_1300 = datetime(2026, 8, 21, 13, 0) # Aug 21, 2026 is a Friday
    assert is_news_blackout(friday_1300, settings) == True
    
    # A Friday at 11:00
    friday_1100 = datetime(2026, 8, 21, 11, 0)
    assert is_news_blackout(friday_1100, settings) == False

def test_trend_state_machine():
    # Build a simple dataframe to mock structure
    # Up move:
    highs = [1, 2, 3, 2, 5, 4, 7]
    lows = [0, 1, 2, 1, 4, 3, 6]
    df = pd.DataFrame({"high": highs, "low": lows, "close": highs})
    df['adx'] = 30 # mock strong trend
    
    # Monkeypatch calculate_adx to just return df
    import strategy.trend
    original_calc = strategy.trend.calculate_adx
    strategy.trend.calculate_adx = lambda x, y: x
    
    # Because analyze_structure uses rolling windows (window=3), we need enough data
    # Let's just create a larger mock manually to ensure we have swings
    dummy_prices = [1]*50
    df_long = pd.DataFrame({
        "high": dummy_prices + [1,2,3,4,3,2,1, 10,12,14,13,12,11, 20,22,24,23,22,21],
        "low":  dummy_prices + [0,1,2,3,2,1,0,  9,11,13,12,11,10, 19,21,23,22,21,20],
        "close":dummy_prices + [1,2,3,4,3,2,1, 10,12,14,13,12,11, 20,22,24,23,22,21]
    })
    df_long['adx'] = 30

    state = determine_trend_state(df_long, settings)
    assert state["state"] == "active_bullish" # Should detect HH and HL sequences
    
    strategy.trend.calculate_adx = original_calc
    
    # Restore
    strategy.trend.calculate_adx = original_calc
