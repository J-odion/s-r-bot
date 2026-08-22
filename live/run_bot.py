import os
import sys
import time
from datetime import datetime, timedelta
import MetaTrader5 as mt5
import pandas as pd
import numpy as np

# Adjust path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config.settings as config
from data.fetch import connect_mt5, TIMEFRAME_MAP
from strategy.sr_levels import detect_multi_timeframe_zones
from strategy.signal_engine import generate_signal
from risk.risk_manager import RiskManager
from execution.mt5_executor import MT5Executor
from live.logger import logger
from data.news_feed import get_upcoming_news, get_news_bias

def fetch_current_data(symbol, timeframes):
    data_dict = {}
    for tf_str in timeframes:
        tf = TIMEFRAME_MAP[tf_str]
        count = 1000 if tf_str in ["MN1", "W1", "D1"] else 200
        rates = mt5.copy_rates_from_pos(symbol, tf, 0, count)
        if rates is None:
            logger.error(f"Failed to fetch {tf_str} data.")
            return None
        df = pd.DataFrame(rates)
        df['time'] = pd.to_datetime(df['time'], unit='s')
        data_dict[tf_str] = df
    return data_dict

def update_baseline_spread(spread_history, current_spread):
    """Maintain a rolling list of recent non-news spreads."""
    spread_history.append(current_spread)
    if len(spread_history) > 100:
        spread_history.pop(0)
    return np.median(spread_history) if spread_history else current_spread

def run_loop():
    if not connect_mt5():
        logger.error("Failed to connect to MT5. Exiting.")
        return
        
    logger.info(f"Starting XAUUSDm Bot on {config.SYMBOL}...")
    
    risk_manager = RiskManager(config)
    executor = MT5Executor(config.SYMBOL, risk_manager)
    
    candidate_signal = None
    candidate_time = None
    
    spread_history = []
    baseline_spread = config.BACKTEST_SPREAD_POINTS # Initial guess
    
    # Track news state
    news_wait_start = None
    
    try:
        while True:
            current_time = datetime.now()
            
            # Update spread baseline
            symbol_info = mt5.symbol_info(config.SYMBOL)
            if symbol_info:
                current_spread = symbol_info.spread
                # Simplistic tracking: update if no news event is actively pending
                baseline_spread = update_baseline_spread(spread_history, current_spread)
                
            # 1. Check for Pre-News Closure
            upcoming_events = get_upcoming_news(config)
            for event in upcoming_events:
                # If we are within NEWS_PRECLOSE_MINUTES of an event
                if 0 <= (event["time"] - current_time).total_seconds() <= config.NEWS_PRECLOSE_MINUTES * 60:
                    logger.info(f"Approaching high-impact news ({event['event']}). Closing open positions.")
                    executor.close_all_positions()
                    candidate_signal = None # Discard pending
            
            # 2. Check Spread Normalization if waiting post-news
            # In a real system, we'd transition into news_wait_start as news happens.
            # Simplified for v1:
            if news_wait_start is not None:
                elapsed = (current_time - news_wait_start).total_seconds()
                
                if elapsed > config.NEWS_MAX_WAIT_MINUTES * 60:
                    logger.warning("Spread never normalized within max wait. Resuming normal operations.")
                    news_wait_start = None
                elif elapsed > config.NEWS_MIN_WAIT_SECONDS:
                    if current_spread <= baseline_spread * config.SPREAD_NORMALIZATION_FACTOR:
                        logger.info("Spread normalized post-news.")
                        news_wait_start = None
                        
                if news_wait_start is not None:
                    time.sleep(15)
                    continue # Skip entry logic while spread is crazy
            
            # Fetch data
            data_dict = fetch_current_data(config.SYMBOL, config.SR_TIMEFRAMES)
            
            if data_dict:
                # We need to detect M5 candle close
                df_m5 = data_dict["M5"]
                current_m5_time = df_m5.iloc[-1]['time']
                
                # If we have a candidate signal from a previous candle, and now a NEW candle has closed
                if candidate_signal and current_m5_time > candidate_time:
                    logger.info("Candidate signal M5 candle closed. Running confirmation check.")
                    
                    all_zones = detect_multi_timeframe_zones(data_dict, config)
                    confirmation_signal = generate_signal(data_dict, all_zones, config)
                    
                    if confirmation_signal and confirmation_signal["direction"] == candidate_signal["direction"]:
                        # Additionally, check news direction if currently acting around news
                        # For v1, if get_news_bias returns 'neutral', it passes. 
                        # If a news event is active, it must match.
                        
                        logger.info(f"Signal confirmed on next candle: {confirmation_signal}")
                        executor.execute_signal(confirmation_signal)
                    else:
                        logger.info("Signal failed confirmation on next candle. Discarding.")
                        
                    candidate_signal = None
                    candidate_time = None
                    
                # If no candidate signal, check if we should create one
                elif not candidate_signal:
                    all_zones = detect_multi_timeframe_zones(data_dict, config)
                    new_signal = generate_signal(data_dict, all_zones, config)
                    
                    if new_signal:
                        logger.info(f"Candidate signal generated, pending confirmation: {new_signal}")
                        candidate_signal = new_signal
                        candidate_time = current_m5_time
            
            # Polling delay
            time.sleep(15) 
            
    except KeyboardInterrupt:
        logger.info("Bot stopped by user.")
    finally:
        mt5.shutdown()

if __name__ == "__main__":
    run_loop()
