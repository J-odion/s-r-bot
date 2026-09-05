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
from execution.scalp_manager import ScalpManager
from strategy.ict_engine import ICTEngine
from live.logger import logger
from data.news_feed import get_upcoming_news, get_news_bias
from live.telegram_notifier import send_telegram_message

def fetch_current_data(symbol, timeframes):
    data_dict = {}
    for tf_str in timeframes:
        tf = TIMEFRAME_MAP.get(tf_str, mt5.TIMEFRAME_M5)
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
    from dotenv import load_dotenv
    load_dotenv() # Ensure .env is loaded
    
    if not connect_mt5():
        logger.error("Failed to connect to MT5. Exiting.")
        send_telegram_message("Failed to connect to MT5. Bot exiting.")
        return
        
    start_msg = f"Starting XAUUSD Bot on {config.SYMBOL} (S/R + ICT Engines enabled)"
    
    # Fetch account info for startup message
    account_info = mt5.account_info()
    if account_info:
        start_msg += f"\n💰 Balance: ${account_info.balance:.2f}"
        start_msg += f"\n📈 Equity: ${account_info.equity:.2f}"
        start_msg += f"\n🛡️ Free Margin: ${account_info.margin_free:.2f}"
        
    logger.info(start_msg.replace('\n', ' | '))
    send_telegram_message(start_msg)
    
    risk_manager = RiskManager(config)
    executor = MT5Executor(config.SYMBOL, risk_manager)
    scalp_manager = ScalpManager(executor, profit_trigger_pips=20, scalp_sl_pips=10, scalp_tp_pips=40, max_scalps=3)
    ict_engine = ICTEngine()
    
    candidate_signal = None
    candidate_time = None
    
    spread_history = []
    baseline_spread = getattr(config, 'BACKTEST_SPREAD_POINTS', 30)
    
    # Track news state
    news_wait_start = None
    
    try:
        while True:
            current_time = datetime.now()
            
            # --- Active Trade & Scalp Manager Check ---
            positions = mt5.positions_get(symbol=config.SYMBOL)
            if positions is not None and len(positions) > 0:
                pos_dicts = [pos._asdict() for pos in positions]
                
                # Log active trade summary to terminal
                acc_info = mt5.account_info()
                if acc_info:
                    total_profit = sum(pos.profit for pos in positions)
                    logger.info(f"--- ACTIVE TRADES ({len(positions)}) ---")
                    logger.info(f"Balance: ${acc_info.balance:.2f} | Equity: ${acc_info.equity:.2f} | Free Margin: ${acc_info.margin_free:.2f}")
                    logger.info(f"Floating PnL: ${total_profit:.2f}")
                    for p in positions:
                        dir_str = "BUY" if p.type == 0 else "SELL"
                        logger.info(f"[{p.ticket}] {dir_str} {p.volume} @ {p.price_open} | Current: {p.price_current} | Profit: ${p.profit:.2f}")
                
                # Scalp manager
                tick = mt5.symbol_info_tick(config.SYMBOL)
                if tick:
                    current_price = {'bid': tick.bid, 'ask': tick.ask}
                    scalp_manager.manage_scalps(current_price, pos_dicts)
            else:
                scalp_manager.reset()
            
            # Update spread baseline
            symbol_info = mt5.symbol_info(config.SYMBOL)
            current_spread = 30
            if symbol_info:
                current_spread = symbol_info.spread
                baseline_spread = update_baseline_spread(spread_history, current_spread)
                
            # 1. Check for Pre-News Closure
            upcoming_events = get_upcoming_news(config)
            for event in upcoming_events:
                # If we are within NEWS_PRECLOSE_MINUTES of an event
                preclose = getattr(config, 'NEWS_PRECLOSE_MINUTES', 10)
                if 0 <= (event["time"] - current_time).total_seconds() <= preclose * 60:
                    logger.info(f"Approaching high-impact news ({event['event']}). Closing open positions.")
                    executor.close_all_positions()
                    candidate_signal = None
            
            # Fetch data for strategies
            # We need standard S/R timeframes + whatever ICT needs (usually M5, M15)
            tf_list = list(set(config.SR_TIMEFRAMES + ["M5", "M15"]))
            data_dict = fetch_current_data(config.SYMBOL, tf_list)
            
            if data_dict and "M5" in data_dict:
                df_m5 = data_dict["M5"]
                current_m5_time = df_m5.iloc[-1]['time']
                
                # --- S/R Strategy Engine ---
                if candidate_signal and current_m5_time > candidate_time:
                    logger.info("Candidate signal M5 candle closed. Running confirmation check.")
                    all_zones = detect_multi_timeframe_zones(data_dict, config)
                    confirmation_signal = generate_signal(data_dict, all_zones, config)
                    
                    if confirmation_signal and confirmation_signal["direction"] == candidate_signal["direction"]:
                        confirmation_signal['magic'] = 1001 # S/R Magic
                        logger.info(f"Signal confirmed on next candle: {confirmation_signal}")
                        executor.execute_signal(confirmation_signal)
                    else:
                        logger.info("Signal failed confirmation on next candle. Discarding.")
                        
                    candidate_signal = None
                    candidate_time = None
                    
                elif not candidate_signal:
                    all_zones = detect_multi_timeframe_zones(data_dict, config)
                    new_signal = generate_signal(data_dict, all_zones, config)
                    if new_signal:
                        logger.info(f"S/R Candidate signal generated, pending confirmation: {new_signal}")
                        candidate_signal = new_signal
                        candidate_time = current_m5_time
                        
                # --- ICT Strategy Engine ---
                # ICT evaluation is standalone and doesn't use the 1-candle confirmation delay in this simplified flow
                ict_signal, ict_reason, ict_entry = ict_engine.evaluate(df_m5)
                if ict_signal != 0:
                    logger.info(f"ICT Signal Detected: {ict_reason} at {ict_entry}")
                    
                    # Construct a standard signal format for the executor
                    direction_str = "bullish" if ict_signal == 1 else "bearish"
                    sl_level = df_m5.iloc[-1]['low'] - 1.0 if ict_signal == 1 else df_m5.iloc[-1]['high'] + 1.0
                    tp_level = ict_entry + 10.0 if ict_signal == 1 else ict_entry - 10.0 # Standard 10 point ICT target for now
                    
                    signal_dict = {
                        "direction": direction_str,
                        "entry": ict_entry,
                        "sl": sl_level,
                        "tp": tp_level,
                        "magic": 1002 # ICT Magic
                    }
                    executor.execute_signal(signal_dict)
            
            # Polling delay & Heartbeat
            logger.info("Building setups... Scanning for S/R and ICT triggers...")
            time.sleep(15)  
            
    except KeyboardInterrupt:
        logger.info("Bot stopped by user.")
    finally:
        mt5.shutdown()

if __name__ == "__main__":
    run_loop()
