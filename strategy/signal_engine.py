from .sr_levels import get_next_target_zone
from .trend import get_aligned_trend
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
    trend_state = get_aligned_trend(df_d1, df_w1, config)
    if trend_state == "conflicted":
        return None # Avoid trading in conflicted trends (can be config driven)
        
    trade_direction = 1 if trend_state == "aligned_bullish" else -1 if trend_state == "aligned_bearish" else 0
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
        
    # 3. Gaps/Sweeps (Optional Filters, currently just logging/scoring)
    # This is a simplified check. A full implementation would deeply integrate these.
    # For now, we'll just require being at a zone in the direction of the trend.
    
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
