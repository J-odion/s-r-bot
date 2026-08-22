import pandas as pd

def detect_sweeps(df, target_levels, threshold_points, max_candles=3):
    """
    Detects if price sweeps a target level and reverses.
    target_levels is a list of important price levels (e.g. prior day high/low, round numbers)
    """
    # This is a complex logic to vectorize purely. We'll do a simplified sliding window check for the current state.
    # A more robust approach requires checking each recent candle against the levels.
    
    # For now, we will return a simple function that checks the last N candles for a sweep of ANY provided level.
    # True if swept, False otherwise.
    
    if len(df) < max_candles + 1:
        return False
        
    recent_candles = df.tail(max_candles + 1)
    
    for level in target_levels:
        # Check bullish sweep (sweeps below level, closes above)
        swept_below = any(recent_candles['low'] < (level - threshold_points))
        closed_above = recent_candles.iloc[-1]['close'] > level
        if swept_below and closed_above:
            return {"type": "bullish", "level": level}
            
        # Check bearish sweep (sweeps above level, closes below)
        swept_above = any(recent_candles['high'] > (level + threshold_points))
        closed_below = recent_candles.iloc[-1]['close'] < level
        if swept_above and closed_below:
            return {"type": "bearish", "level": level}
            
    return None
