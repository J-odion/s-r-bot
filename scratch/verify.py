import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config.settings as config
from strategy.sr_levels import get_next_target_zone
from risk.risk_manager import RiskManager

def test_tier_settings():
    print("--- S/R Tier Settings Check ---")
    for tier, settings in config.SR_TIER_SETTINGS.items():
        print(f"Tier: {tier}, Window: {settings['window']}, Tolerance: {settings['tolerance']}")
    print("")

def test_tp_preference():
    print("--- Take-Profit Preference Check ---")
    zones = [
        {"level": 2400.0, "timeframe": "M5", "lower": 2399.0, "upper": 2401.0},
        {"level": 2405.0, "timeframe": "M15", "lower": 2404.0, "upper": 2406.0},
        {"level": 2410.0, "timeframe": "D1", "lower": 2408.0, "upper": 2412.0},
    ]
    tp1 = get_next_target_zone(2390.0, 1, zones, "M5")
    print(f"Long from 2390. M5 is closest. Next D1 is 2410. Between 2390 and 2410, is there an intraday zone? Yes, M5 at 2400. Selected TP timeframe: {tp1['timeframe']} at {tp1['level']}")
    
    tp2 = get_next_target_zone(2406.0, 1, zones, "M15")
    print(f"Long from 2406. Next D1 is 2410. Between 2406 and 2410, is there an intraday zone? No. Selected TP timeframe: {tp2['timeframe']} at {tp2['level']}")
    print("")

def test_risk_manager():
    print("--- Risk Manager Pos Limit Check ---")
    rm = RiskManager(config)
    class MockMT5:
        def positions_get(self, symbol):
            class MockPos:
                pass
            return [MockPos()]
    import MetaTrader5
    original_mt5 = MetaTrader5.positions_get
    MetaTrader5.positions_get = MockMT5().positions_get
    
    can_trade = rm.can_trade("XAUUSDm")
    print(f"Can trade with 1 open position? {can_trade}")
    MetaTrader5.positions_get = original_mt5
    print("")

if __name__ == "__main__":
    test_tier_settings()
    test_tp_preference()
    try:
        test_risk_manager()
    except Exception as e:
        print(f"MT5 mocking failed: {e}")
