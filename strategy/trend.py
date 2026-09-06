import pandas as pd
import numpy as np

def calculate_adx(df, period=14):
    """Calculates ADX and adds it to the dataframe."""
    df = df.copy()
    
    tr0 = abs(df['high'] - df['low'])
    tr1 = abs(df['high'] - df['close'].shift(1))
    tr2 = abs(df['low'] - df['close'].shift(1))
    df['tr'] = pd.concat([tr0, tr1, tr2], axis=1).max(axis=1)
    
    df['up_move'] = df['high'] - df['high'].shift(1)
    df['down_move'] = df['low'].shift(1) - df['low']
    
    df['plus_dm'] = np.where((df['up_move'] > df['down_move']) & (df['up_move'] > 0), df['up_move'], 0)
    df['minus_dm'] = np.where((df['down_move'] > df['up_move']) & (df['down_move'] > 0), df['down_move'], 0)
    
    df['atr'] = df['tr'].ewm(alpha=1/period, adjust=False).mean()
    df['plus_di'] = 100 * (df['plus_dm'].ewm(alpha=1/period, adjust=False).mean() / df['atr'])
    df['minus_di'] = 100 * (df['minus_dm'].ewm(alpha=1/period, adjust=False).mean() / df['atr'])
    
    df['dx'] = 100 * abs(df['plus_di'] - df['minus_di']) / (df['plus_di'] + df['minus_di'])
    df['adx'] = df['dx'].ewm(alpha=1/period, adjust=False).mean()
    
    return df

def analyze_structure(df):
    """
    Analyzes trend bias using 20 and 50 period EMAs.
    """
    if len(df) < 50:
         return {"bias": "neutral"}
         
    ema20 = df['close'].ewm(span=20, adjust=False).mean()
    ema50 = df['close'].ewm(span=50, adjust=False).mean()
    
    current_ema20 = ema20.iloc[-1]
    current_ema50 = ema50.iloc[-1]
    
    if current_ema20 > current_ema50:
        return {"bias": "bullish"}
    elif current_ema20 < current_ema50:
        return {"bias": "bearish"}
    else:
        return {"bias": "neutral"}

def get_regime_state(df, config):
    """
    Returns the Master Strategy regime state based on ADX and Structure.
    Returns: {"regime": "trending" | "ranging", "bias": "bullish" | "bearish" | "neutral", "atr": float}
    """
    if len(df) < 50:
        return {"regime": "ranging", "bias": "neutral", "atr": 0.0}
        
    df = calculate_adx(df, config.ADX_PERIOD)
    current_adx = df.iloc[-1]['adx']
    current_atr = df.iloc[-1]['atr']
    
    regime = "trending" if current_adx >= 25 else "ranging"
    
    structure = analyze_structure(df)
    bias = structure["bias"]
            
    return {"regime": regime, "bias": bias, "atr": current_atr}
