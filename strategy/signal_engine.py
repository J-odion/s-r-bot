from .sr_levels import get_next_target_zone
from .trend import get_regime_state
from .liquidity_gaps import detect_price_gaps, detect_fvg
from .liquidity_sweeps import detect_sweeps
from .stop_loss import calculate_structural_sl

def generate_signal(data_dict, all_zones, config):
    """
    Orchestrates the rules to generate a trading signal.
    data_dict contains current dataframes for different timeframes.
    Returns a dict with signal details if a valid setup is found, else None.
    """
    df_m5 = data_dict.get("M5")
    df_d1 = data_dict.get("D1")
    df_w1 = data_dict.get("W1")
    
    if df_m5 is None or df_d1 is None or df_w1 is None:
        return None
        
    current_price = df_m5.iloc[-1]['close']
    
    # 1. Trend Alignment
    # Cache the trend state to avoid recomputing ADX millions of times
    global _cached_trend_state
    global _cached_trend_time
    try:
        last_d1_time = df_d1.index[-1] if not 'time' in df_d1.columns else df_d1.iloc[-1]['time']
        if _cached_trend_time == last_d1_time:
            trend_state = _cached_trend_state
        else:
            trend_result = get_regime_state(df_d1, config)
            trend_state = trend_result["bias"]
            _cached_trend_time = last_d1_time
            _cached_trend_state = trend_state
    except NameError:
        _cached_trend_time = None
        trend_result = get_regime_state(df_d1, config)
        trend_state = trend_result["bias"]
        
    if trend_state == "neutral":
        return None # Avoid trading in conflicted trends (can be config driven)
        
    trade_direction = 1 if trend_state == "bullish" else -1 if trend_state == "bearish" else 0
    if trade_direction == 0:
        return None
        
    # 2. Support & Resistance Check (Are we at a zone?)
    active_zone = None
    for z in all_zones:
        # Check if current price is within the zone bounds
        if z["lower"] <= current_price <= z["upper"]:
            active_zone = z
            break
            
    if not active_zone:
        return None # No entry if not reacting at a valid zone
        
    # Cooldown Check: 4 hours (14400 seconds)
    global _zone_cooldowns
    try:
        _zone_cooldowns
    except NameError:
        _zone_cooldowns = {}
        
    zone_key = round(active_zone["level"], 3)
    current_time = df_m5.index[-1] if not 'time' in df_m5.columns else df_m5.iloc[-1]['time']
    
    if zone_key in _zone_cooldowns:
        time_since = (current_time - _zone_cooldowns[zone_key]).total_seconds()
        if time_since < 4 * 3600:
            return None # Cooldown active
            
    # Confirmation Candle Check
    current = df_m5.iloc[-1]
    prev = df_m5.iloc[-2]
    
    body = abs(current['open'] - current['close'])
    range_total = current['high'] - current['low']
    if range_total == 0:
        return None
        
    body_fraction = body / range_total
    
    is_bullish_engulfing = (current['close'] > current['open'] and 
                            prev['close'] < prev['open'] and
                            current['close'] > prev['open'] and 
                            current['open'] < prev['close'] and 
                            body_fraction > 0.5)
                            
    is_bearish_engulfing = (current['close'] < current['open'] and 
                            prev['close'] > prev['open'] and
                            current['close'] < prev['open'] and 
                            current['open'] > prev['close'] and 
                            body_fraction > 0.5)
                            
    lower_wick = min(current['open'], current['close']) - current['low']
    upper_wick = current['high'] - max(current['open'], current['close'])
    
    is_bullish_pinbar = (lower_wick > 2 * body) and (upper_wick < body)
    is_bearish_pinbar = (upper_wick > 2 * body) and (lower_wick < body)
    
    if trade_direction == 1 and not (is_bullish_engulfing or is_bullish_pinbar):
        return None
    if trade_direction == -1 and not (is_bearish_engulfing or is_bearish_pinbar):
        return None
        
    # Update cooldown
    _zone_cooldowns[zone_key] = current_time
    
    # Calculate SL
    sl_price = calculate_structural_sl(df_m5, -1, trade_direction, config.SL_BUFFER_POINTS)
    if sl_price is None:
         return None
         
    # Determine Target
    target_zone = get_next_target_zone(current_price, trade_direction, all_zones, active_zone["timeframe"])
    tp_price = target_zone["level"] if target_zone else None
    
    # If no target zone is found ahead, do not generate a signal (or use a fallback, but sticking to strict rules here)
    if tp_price is None:
        return None
    
    return {
        "direction": "buy" if trade_direction == 1 else "sell",
        "entry_price": current_price,
        "sl_price": sl_price,
        "tp_price": tp_price,
        "zone_timeframe": active_zone["timeframe"],
        "confluence_score": active_zone["confluence_score"]
    }
