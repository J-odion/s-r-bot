import pandas as pd

def detect_price_gaps(df, threshold_points):
    """
    Detects simple price gaps between sessions/candles.
    Returns a series or adds a column to df.
    """
    df = df.copy()
    # A gap is when the current open is significantly different from the previous close.
    df['gap_up'] = (df['open'] - df['close'].shift(1)) > threshold_points
    df['gap_down'] = (df['close'].shift(1) - df['open']) > threshold_points
    return df

def detect_fvg(df):
    """
    Detects Fair Value Gaps (3-candle imbalance).
    """
    df = df.copy()
    # Bullish FVG: Candle 1 High < Candle 3 Low
    # Bearish FVG: Candle 1 Low > Candle 3 High
    
    c1_high = df['high'].shift(2)
    c1_low = df['low'].shift(2)
    c3_high = df['high']
    c3_low = df['low']
    
    df['fvg_bullish'] = c1_high < c3_low
    df['fvg_bearish'] = c1_low > c3_high
    
    return df
