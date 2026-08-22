import pandas as pd
import numpy as np

def detect_swing_points(df, window=5):
    """
    Detects swing highs and lows in a dataframe.
    A swing high is the highest high within a window before and after it.
    """
    df = df.copy()
    
    # Using rolling windows to find local extrema
    # For a high to be a swing high, it must be higher than 'window' periods before and after
    df['is_swing_high'] = False
    df['is_swing_low'] = False
    
    # We iterate over the series (can be vectorized but iteration is simpler to read for exact window logic)
    # A faster vectorized way using rolling:
    highs = df['high'].rolling(window=2*window+1, center=True).max()
    lows = df['low'].rolling(window=2*window+1, center=True).min()
    
    df.loc[df['high'] == highs, 'is_swing_high'] = True
    df.loc[df['low'] == lows, 'is_swing_low'] = True
    
    return df

def cluster_swings(swings, tolerance):
    """
    Clusters swing prices that are within a certain tolerance band of each other.
    Returns a list of zones.
    """
    if not swings:
        return []
        
    swings = sorted(swings)
    zones = []
    
    current_zone_start = swings[0]
    current_zone_prices = [swings[0]]
    
    for price in swings[1:]:
        # If the price is within the tolerance band of the start of the current zone
        if price <= current_zone_start * (1 + tolerance):
            current_zone_prices.append(price)
        else:
            # Finalize current zone
            zone_center = sum(current_zone_prices) / len(current_zone_prices)
            zones.append({
                "price": zone_center,
                "upper": max(current_zone_prices),
                "lower": min(current_zone_prices),
                "touch_count": len(current_zone_prices)
            })
            # Start new zone
            current_zone_start = price
            current_zone_prices = [price]
            
    # Add last zone
    if current_zone_prices:
        zone_center = sum(current_zone_prices) / len(current_zone_prices)
        zones.append({
            "price": zone_center,
            "upper": max(current_zone_prices),
            "lower": min(current_zone_prices),
            "touch_count": len(current_zone_prices)
        })
        
    return zones

def get_zones_for_timeframe(df, tolerance, timeframe_label, window):
    df_swings = detect_swing_points(df, window=window)
    
    # Extract just the prices
    swing_highs = df_swings[df_swings['is_swing_high']]['high'].tolist()
    swing_lows = df_swings[df_swings['is_swing_low']]['low'].tolist()
    
    all_swings = swing_highs + swing_lows
    
    zones = cluster_swings(all_swings, tolerance)
    
    # Format them
    formatted_zones = []
    for z in zones:
        formatted_zones.append({
            "level": z["price"],
            "upper": z["upper"],
            "lower": z["lower"],
            "timeframe": timeframe_label,
            "touch_count": z["touch_count"],
            "confluence_score": 0,
            "is_confirmed": z["touch_count"] >= 2
        })
        
    return formatted_zones

def detect_multi_timeframe_zones(data_dict, config):
    """
    data_dict contains dataframes keyed by timeframe e.g. "D1", "W1", "MN1"
    """
    all_zones = []
    
    # Process standard timeframes
    for tf in ["MN1", "W1", "D1", "H4", "H1", "M15", "M5"]:
        if tf in data_dict:
            # Map standard TF to setting tier
            if tf in ["MN1", "W1", "D1"]:
                tier = tf
            else:
                tier = "Intraday"
                
            tier_settings = config.SR_TIER_SETTINGS[tier]
            zones = get_zones_for_timeframe(data_dict[tf], tier_settings["tolerance"], tf, tier_settings["window"])
            all_zones.extend(zones)
            
    # Derive Yearly zones from MN1 data (using the Yearly window/tolerance on the MN1 dataframe)
    if "MN1" in data_dict:
        y_settings = config.SR_TIER_SETTINGS["Yearly"]
        yearly_zones = get_zones_for_timeframe(data_dict["MN1"], y_settings["tolerance"], "Yearly", y_settings["window"])
        all_zones.extend(yearly_zones)
            
    # Calculate Confluence: if a lower TF zone (e.g. D1/W1) is near a higher TF zone (MN1/Yearly)
    higher_tf_zones = [z for z in all_zones if z["timeframe"] in ["MN1", "Yearly"]]
    
    for z in all_zones:
        if z["timeframe"] not in ["MN1", "Yearly"]:
            for hz in higher_tf_zones:
                if hz["timeframe"] == z["timeframe"]:
                    continue # Skip same tf
                
                # If z level is within bounds of hz level +/- tolerance
                if abs(z["level"] - hz["level"]) / hz["level"] <= 0.002:
                    z["confluence_score"] += 1
                    
    return all_zones

def get_next_target_zone(current_price, trade_direction, all_zones, active_zone_timeframe=None):
    """
    trade_direction: 1 (long) or -1 (short)
    Find nearest untested zone ahead of price.
    Prefer D1/W1 targets for intraday entries unless an intraday zone is between.
    """
    valid_zones = []
    for z in all_zones:
        if trade_direction == 1 and z["lower"] > current_price:
            valid_zones.append(z)
        elif trade_direction == -1 and z["upper"] < current_price:
            valid_zones.append(z)
            
    if not valid_zones:
        return None
        
    # Sort by proximity to current price
    valid_zones.sort(key=lambda z: abs(z["level"] - current_price))
    
    # Task 2: Take-Profit Preference
    # If it's an intraday entry, we prefer D1/W1, unless an intraday is strictly closer.
    # Since we sorted by proximity, valid_zones[0] is the absolute closest.
    # The requirement says "prefer the next Daily or Weekly zone as target; 
    # only fall back to a closer intraday zone if one genuinely sits between entry and that Daily/Weekly zone."
    # Because valid_zones[0] is mathematically between entry and any further D1/W1 zone,
    # simply returning valid_zones[0] exactly fulfills this logical requirement.
    # However, to be explicit in following the instruction "explicitly search for the next D1/W1 zone first":
    
    if active_zone_timeframe in ["M5", "M15", "H1", "H4", "Intraday"]:
        # Find the first D1/W1 zone
        next_d1_w1 = None
        for z in valid_zones:
            if z["timeframe"] in ["D1", "W1", "MN1", "Yearly"]:
                next_d1_w1 = z
                break
                
        if next_d1_w1:
            # Check if there is an intraday zone closer than next_d1_w1
            for z in valid_zones:
                if z["timeframe"] in ["M5", "M15", "H1", "H4", "Intraday"]:
                    if abs(z["level"] - current_price) < abs(next_d1_w1["level"] - current_price):
                        # Yes, an intraday is genuinely sitting between
                        return z
            # Otherwise, use the D1/W1 target
            return next_d1_w1
            
    return valid_zones[0]
