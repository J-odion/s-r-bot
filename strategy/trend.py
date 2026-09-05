import pandas as pd
import numpy as np

def calculate_adx(df, period=14):
    """Calculates ADX and adds it to the dataframe."""
    df = df.copy()
    
    # Calculate True Range
    df['tr0'] = abs(df['high'] - df['low'])
    df['tr1'] = abs(df['high'] - df['close'].shift(1))
    df['tr2'] = abs(df['low'] - df['close'].shift(1))
    df['tr'] = df[['tr0', 'tr1', 'tr2']].max(axis=1)
    
    # Calculate Directional Movement
    df['up_move'] = df['high'] - df['high'].shift(1)
    df['down_move'] = df['low'].shift(1) - df['low']
    
    df['plus_dm'] = np.where((df['up_move'] > df['down_move']) & (df['up_move'] > 0), df['up_move'], 0)
    df['minus_dm'] = np.where((df['down_move'] > df['up_move']) & (df['down_move'] > 0), df['down_move'], 0)
    
    # Smoothed TR and DM
    df['atr'] = df['tr'].ewm(alpha=1/period, adjust=False).mean()
    df['plus_di'] = 100 * (df['plus_dm'].ewm(alpha=1/period, adjust=False).mean() / df['atr'])
    df['minus_di'] = 100 * (df['minus_dm'].ewm(alpha=1/period, adjust=False).mean() / df['atr'])
    
    # Calculate ADX
    df['dx'] = 100 * abs(df['plus_di'] - df['minus_di']) / (df['plus_di'] + df['minus_di'])
    df['adx'] = df['dx'].ewm(alpha=1/period, adjust=False).mean()
    
    return df

def analyze_structure(df):
    """
    Analyzes HH/HL or LH/LL structure to determine trend direction.
    Uses simple swing logic similar to sr_levels.
    """
    window = 3 # Smaller window for trend structure swings
    highs = df['high'].rolling(window=2*window+1, center=True).max()
    lows = df['low'].rolling(window=2*window+1, center=True).min()
    
    swing_highs = df[df['high'] == highs].copy()
    swing_lows = df[df['low'] == lows].copy()
    
    if len(swing_highs) < 3 or len(swing_lows) < 3:
         return {"bias": "neutral", "last_hl": None, "last_lh": None}
         
    # Check last three swing highs and lows to get the full transition
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
        bias = "terminating_bullish" # Was bullish, last swing broke it
    elif is_lh1 and is_ll1:
        bias = "terminating_bearish" # Was bearish, last swing broke it
        
    return {
        "bias": bias, 
        "last_hl": last_lows[2] if bias == "bullish" else (last_lows[1] if bias == "terminating_bullish" else None),
        "last_lh": last_highs[2] if bias == "bearish" else (last_highs[1] if bias == "terminating_bearish" else None)
    }
    
def _determine_trend_state_core(df, config):
    """Core logic to evaluate the trend state string."""
    df = calculate_adx(df, config.ADX_PERIOD)
    current_adx = df.iloc[-1]['adx']
    
    if current_adx < config.ADX_THRESHOLD:
         return "neutral"
         
    structure = analyze_structure(df)
    bias = structure["bias"]
    current_close = df.iloc[-1]['close']
    
    state = "neutral"
    if bias == "bullish":
        if current_close < structure["last_hl"]:
            state = "terminated"
        else:
            state = "active_bullish"
    elif bias == "bearish":
        if current_close > structure["last_lh"]:
            state = "terminated"
        else:
            state = "active_bearish"
    elif bias == "terminating_bullish":
        if current_close < structure["last_hl"]:
            state = "terminated"
    elif bias == "terminating_bearish":
        if current_close > structure["last_lh"]:
            state = "terminated"
            
    return state

def determine_trend_state(df, config):
    """
    Evaluates trend state and termination.
    State machine: active -> terminated -> reversal_confirmed
    Returns a dict with state and flags.
    """
    if len(df) < 50:
        return {"state": "neutral", "reversal_just_confirmed": False}
        
    current_state = _determine_trend_state_core(df, config)
    previous_state = _determine_trend_state_core(df.iloc[:-1], config)
    
    reversal_just_confirmed = False
    
    # Fix 1: Flag is only true if we just transitioned out of a terminated/terminating state
    # into a new active state in the opposite direction (or from neutral/terminated to active)
    terminating_states = ["terminated", "terminating_bearish", "terminating_bullish", "neutral"]
    
    if current_state == "active_bullish" and previous_state in terminating_states:
        reversal_just_confirmed = True
    elif current_state == "active_bearish" and previous_state in terminating_states:
        reversal_just_confirmed = True
            
    return {"state": current_state, "reversal_just_confirmed": reversal_just_confirmed}

def get_aligned_trend(df_daily, df_weekly, config):
    """Checks alignment between daily and weekly trend."""
    daily_res = determine_trend_state(df_daily, config)
    weekly_res = determine_trend_state(df_weekly, config)
    
    daily_state = daily_res["state"]
    weekly_state = weekly_res["state"]
    
    # Check if either just confirmed a reversal
    just_confirmed = daily_res["reversal_just_confirmed"] or weekly_res["reversal_just_confirmed"]
    
    if daily_state == "active_bullish" and weekly_state == "active_bullish":
        return {"alignment": "aligned_bullish", "reversal_just_confirmed": just_confirmed}
    elif daily_state == "active_bearish" and weekly_state == "active_bearish":
        return {"alignment": "aligned_bearish", "reversal_just_confirmed": just_confirmed}
    else:
        return {"alignment": "conflicted", "reversal_just_confirmed": False}
