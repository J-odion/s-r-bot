def calculate_structural_sl(df_m5, entry_index_or_time, trade_direction, buffer_points):
    """
    Calculates the stop loss based on the structure immediately preceding the reaction candle.
    The SL is anchored to the candle just before the entry signal candle.
    """
    # Assuming df_m5 is indexed by time or simple range index, and entry_index points to the signal candle.
    # We need the candle BEFORE the entry candle.
    if len(df_m5) < 2:
        return None
        
    pre_reaction_candle = df_m5.iloc[-2] # Default to the one before the current closing one
    
    if trade_direction == 1: # Long
        sl_price = pre_reaction_candle['low'] - buffer_points
    elif trade_direction == -1: # Short
        sl_price = pre_reaction_candle['high'] + buffer_points
    else:
        sl_price = None
        
    return sl_price
