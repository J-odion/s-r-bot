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
    Analyzes HH/HL or LH/LL structure to determine trend direction.
    """
    window = 3 
    highs = df['high'].rolling(window=2*window+1, center=True).max()
    lows = df['low'].rolling(window=2*window+1, center=True).min()
    
    swing_highs = df[df['high'] == highs].copy()
    swing_lows = df[df['low'] == lows].copy()
    
    if len(swing_highs) < 3 or len(swing_lows) < 3:
         return {"bias": "neutral", "last_hl": None, "last_lh": None}
         
    last_highs = swing_highs.tail(3)['high'].tolist()
    last_lows = swing_lows.tail(3)['low'].tolist()
    
    is_hh1 = last_highs[1] > last_highs[0]
    is_hl1 = last_lows[1] > last_lows[0]
    
    is_hh2 = last_highs[2] > last_highs[1]
    is_hl2 = last_lows[2] > last_lows[1]
    
    is_lh1 = last_highs[1] < last_highs[0]
    is_ll1 = last_lows[1] < last_lows[0]
    
    is_lh2 = last_highs[2] < last_highs[1]
    is_ll2 = last_lows[2] < last_lows[1]
    
    bias = "neutral"
    if is_hh2 and is_hl2:
        bias = "bullish"
    elif is_lh2 and is_ll2:
        bias = "bearish"
    elif is_hh1 and is_hl1:
        bias = "terminating_bullish" 
    elif is_lh1 and is_ll1:
        bias = "terminating_bearish" 
        
    return {
        "bias": bias, 
        "last_hl": last_lows[2] if bias == "bullish" else (last_lows[1] if bias == "terminating_bullish" else None),
        "last_lh": last_highs[2] if bias == "bearish" else (last_highs[1] if bias == "terminating_bearish" else None)
    }

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
    current_close = df.iloc[-1]['close']
    
    state = "neutral"
    if bias == "bullish":
        if current_close < structure["last_hl"]:
            state = "neutral"
        else:
            state = "bullish"
    elif bias == "bearish":
        if current_close > structure["last_lh"]:
            state = "neutral"
        else:
            state = "bearish"
            
    return {"regime": regime, "bias": state, "atr": current_atr}
