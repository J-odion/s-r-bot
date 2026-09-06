import os
import sys
import pandas as pd
import numpy as np
from datetime import datetime

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config.settings as config
from strategy.sr_levels import detect_multi_timeframe_zones
from strategy.signal_engine import generate_signal
from strategy.ict_engine import ICTEngine

def load_data(symbol):
    cache_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'cache')
    data_dict = {}
    for tf in ["M5", "M15", "H1", "H4", "D1", "W1", "MN1"]:
        file_path = os.path.join(cache_dir, f"{symbol}_{tf}.csv")
        if os.path.exists(file_path):
            df = pd.read_csv(file_path, parse_dates=['time'])
            df.set_index('time', inplace=True)
            data_dict[tf] = df
    return data_dict

class CustomBacktester:
    def __init__(self, data_dict, starting_balance=10000.0):
        self.data_dict = data_dict
        self.balance = starting_balance
        self.ict_trades = []
        self.sr_trades = []
        self.active_ict_trade = None
        self.active_sr_trade = None
        self.scalp_trades = []
        self.active_scalps = []
        self.ict_engine = ICTEngine()
        
    def run(self):
        df_m5 = self.data_dict["M5"]
        spread = config.BACKTEST_SPREAD_POINTS / 100.0 # roughly 0.3 for gold (30 points)
        
        # We process the last 10,000 candles for a quick, accurate report
        total_rows = len(df_m5)
        start_idx = total_rows - 10000 if total_rows > 10000 else 500
        print(f"Starting simulation on {total_rows - start_idx} M5 candles...")
        
        sr_candidate_signal = None
        sr_candidate_time = None
        
        for i in range(start_idx, total_rows):
            current_time = df_m5.index[i]
            current_row = df_m5.iloc[i]
            current_close = current_row['close']
            current_high = current_row['high']
            current_low = current_row['low']
            
            # --- Manage Active Trades ---
            if self.active_ict_trade:
                trade = self.active_ict_trade
                if trade['direction'] == 'bullish':
                    if current_low <= trade['sl']:
                        trade['exit_price'] = trade['sl']
                        trade['profit'] = (trade['sl'] - trade['entry_price']) * 0.10 # $0.10 per point for 0.01 lot
                        self.ict_trades.append(trade)
                        self.active_ict_trade = None
                    elif current_high >= trade['tp']:
                        trade['exit_price'] = trade['tp']
                        trade['profit'] = (trade['tp'] - trade['entry_price']) * 0.10
                        self.ict_trades.append(trade)
                        self.active_ict_trade = None
                else:
                    if current_high >= trade['sl']:
                        trade['exit_price'] = trade['sl']
                        trade['profit'] = (trade['entry_price'] - trade['sl']) * 0.10
                        self.ict_trades.append(trade)
                        self.active_ict_trade = None
                    elif current_low <= trade['tp']:
                        trade['exit_price'] = trade['tp']
                        trade['profit'] = (trade['entry_price'] - trade['tp']) * 0.10
                        self.ict_trades.append(trade)
                        self.active_ict_trade = None

            if self.active_sr_trade:
                trade = self.active_sr_trade
                if trade['direction'] == 'bullish':
                    if current_low <= trade['sl']:
                        trade['exit_price'] = trade['sl']
                        trade['profit'] = (trade['sl'] - trade['entry_price']) * 0.10
                        self.sr_trades.append(trade)
                        self.active_sr_trade = None
                    elif current_high >= trade['tp']:
                        trade['exit_price'] = trade['tp']
                        trade['profit'] = (trade['tp'] - trade['entry_price']) * 0.10
                        self.sr_trades.append(trade)
                        self.active_sr_trade = None
                else:
                    if current_high >= trade['sl']:
                        trade['exit_price'] = trade['sl']
                        trade['profit'] = (trade['entry_price'] - trade['sl']) * 0.10
                        self.sr_trades.append(trade)
                        self.active_sr_trade = None
                    elif current_low <= trade['tp']:
                        trade['exit_price'] = trade['tp']
                        trade['profit'] = (trade['entry_price'] - trade['tp']) * 0.10
                        self.sr_trades.append(trade)
                        self.active_sr_trade = None
            
            # --- Manage Scalp Trades ---
            for scalp in list(self.active_scalps):
                if scalp['direction'] == 'bullish':
                    if current_low <= scalp['sl']:
                        scalp['exit_price'] = scalp['sl']
                        scalp['profit'] = (scalp['sl'] - scalp['entry_price']) * 0.10
                        self.scalp_trades.append(scalp)
                        self.active_scalps.remove(scalp)
                    elif current_high >= scalp['tp']:
                        scalp['exit_price'] = scalp['tp']
                        scalp['profit'] = (scalp['tp'] - scalp['entry_price']) * 0.10
                        self.scalp_trades.append(scalp)
                        self.active_scalps.remove(scalp)
                else:
                    if current_high >= scalp['sl']:
                        scalp['exit_price'] = scalp['sl']
                        scalp['profit'] = (scalp['entry_price'] - scalp['sl']) * 0.10
                        self.scalp_trades.append(scalp)
                        self.active_scalps.remove(scalp)
                    elif current_low <= scalp['tp']:
                        scalp['exit_price'] = scalp['tp']
                        scalp['profit'] = (scalp['entry_price'] - scalp['tp']) * 0.10
                        self.scalp_trades.append(scalp)
                        self.active_scalps.remove(scalp)
            
            # --- Open Scalp Trades ---
            # If primary trade is in profit, open up to 3 scalps
            if self.active_sr_trade:
                t = self.active_sr_trade
                if t.get('scalps_taken', 0) < 3:
                    in_profit = False
                    if t['direction'] == 'bullish' and current_close > t['entry_price'] + 2.0:
                        in_profit = True
                    elif t['direction'] == 'bearish' and current_close < t['entry_price'] - 2.0:
                        in_profit = True
                        
                    if in_profit:
                        # Open Scalp
                        scalp_dir = t['direction']
                        scalp_entry = current_close
                        # User requested SL of 5 pips (50 points), TP of 10 pips (100 points)
                        if scalp_dir == 'bullish':
                            scalp_sl = scalp_entry - 5.0
                            scalp_tp = scalp_entry + 10.0
                        else:
                            scalp_sl = scalp_entry + 5.0
                            scalp_tp = scalp_entry - 10.0
                            
                        self.active_scalps.append({
                            'time': current_time,
                            'direction': scalp_dir,
                            'entry_price': scalp_entry,
                            'sl': scalp_sl,
                            'tp': scalp_tp
                        })
                        t['scalps_taken'] = t.get('scalps_taken', 0) + 1
            # Extract trailing data
            trailing_m5 = df_m5.iloc[i-200:i+1]
            
            # --- Evaluate ICT Engine ---
            if not self.active_ict_trade:
                # Add 'time' column back for evaluate
                trailing_m5_with_time = trailing_m5.reset_index()
                ict_signal, ict_reason, ict_entry = self.ict_engine.evaluate(trailing_m5_with_time)
                
                if ict_signal != 0:
                    dir_str = "bullish" if ict_signal == 1 else "bearish"
                    sl = current_low - 1.0 if ict_signal == 1 else current_high + 1.0
                    tp = current_close + 10.0 if ict_signal == 1 else current_close - 10.0
                    entry_price = current_close + spread if ict_signal == 1 else current_close - spread
                    
                    self.active_ict_trade = {
                        'time': current_time,
                        'direction': dir_str,
                        'entry_price': entry_price,
                        'sl': sl,
                        'tp': tp,
                    }
                    
            # --- Evaluate S/R Engine ---
            if i % 12 == 0: # Recalculate zones every hour to save time
                sliced_dict = {}
                for tf, df in self.data_dict.items():
                    sliced_df = df[df.index <= current_time]
                    if len(sliced_df) > 0:
                        sliced_dict[tf] = sliced_df.tail(200).reset_index()
                self.cached_zones = detect_multi_timeframe_zones(sliced_dict, config)
                self.cached_sliced_dict = sliced_dict
            
            if not self.active_sr_trade and hasattr(self, 'cached_zones'):
                # We need to update the M5 data in sliced_dict to the current candle for signal evaluation
                current_m5_slice = trailing_m5.reset_index()
                eval_dict = self.cached_sliced_dict.copy()
                eval_dict["M5"] = current_m5_slice
                
                if sr_candidate_signal and current_time > sr_candidate_time:
                    conf_signal = generate_signal(eval_dict, self.cached_zones, config)
                    if conf_signal and conf_signal["direction"] == sr_candidate_signal["direction"]:
                        dir_str = 'bullish' if conf_signal["direction"] == "buy" else 'bearish'
                        entry_price = current_close + spread if dir_str == 'bullish' else current_close - spread
                        self.active_sr_trade = {
                            'time': current_time,
                            'direction': dir_str,
                            'entry_price': entry_price,
                            'sl': conf_signal["sl_price"],
                            'tp': conf_signal["tp_price"],
                        }
                    sr_candidate_signal = None
                    sr_candidate_time = None
                elif not sr_candidate_signal:
                    new_signal = generate_signal(eval_dict, self.cached_zones, config)
                    if new_signal:
                        sr_candidate_signal = new_signal
                        sr_candidate_time = current_time

    def generate_report(self):
        print("\n==============================================")
        print("          BACKTEST REPORT (10,000 Candles)")
        print("==============================================\n")
        
        self.print_strategy_report("ICT Strategy", self.ict_trades)
        self.print_strategy_report("S/R Strategy", self.sr_trades)
        self.print_strategy_report("Scalp Trades", self.scalp_trades)

    def print_strategy_report(self, name, trades):
        total_trades = len(trades)
        if total_trades == 0:
            print(f"[{name}] No trades executed.")
            print("----------------------------------------------")
            return
            
        wins = [t for t in trades if t['profit'] > 0]
        losses = [t for t in trades if t['profit'] <= 0]
        
        win_rate = (len(wins) / total_trades) * 100
        loss_rate = (len(losses) / total_trades) * 100
        
        # Calculate days
        if trades:
            first_trade = trades[0]['time']
            last_trade = trades[-1]['time']
            total_days = max(1, (last_trade - first_trade).days)
        else:
            total_days = 1
            
        total_profit_usd = sum(t['profit'] for t in wins)
        total_loss_usd = sum(t['profit'] for t in losses)
        net_profit = total_profit_usd + total_loss_usd
        
        print(f"[{name}]")
        print(f"  All Time Total Trades: {total_trades}")
        print(f"  All Time Wins:         {len(wins)}")
        print(f"  All Time Losses:       {len(losses)}")
        print(f"  Win Rate:              {win_rate:.2f}%")
        print(f"  Loss Rate:             {loss_rate:.2f}%")
        print(f"  Total Profit:          ${total_profit_usd:.2f}")
        print(f"  Total Loss:            ${total_loss_usd:.2f}")
        print(f"  Net Profit:            ${net_profit:.2f}")
        print(f"  Avg Trades per Day:    {total_trades / total_days:.2f}")
        print(f"  Avg Profit per Day:    ${total_profit_usd / total_days:.2f}")
        print(f"  Avg Loss per Day:      ${total_loss_usd / total_days:.2f}")
        print(f"  Avg Net Profit/Day:    ${net_profit / total_days:.2f}")
        
        print(f"\n  --- {name} Trade Log ---")
        for i, t in enumerate(trades, 1):
            result = "SUCCESS" if t['profit'] > 0 else "FAILED "
            profit_str = f"+${t['profit']:.2f}" if t['profit'] > 0 else f"-${abs(t['profit']):.2f}"
            print(f"  {i:02d}. {t['time'].strftime('%Y-%m-%d %H:%M')} | {t['direction'].upper():7s} | "
                  f"Entry: {t['entry_price']:.2f} | SL: {t['sl']:.2f} | TP: {t['tp']:.2f} | "
                  f"Exit: {t['exit_price']:.2f} | Result: {result} ({profit_str})")
        
        print("----------------------------------------------")

if __name__ == "__main__":
    # If run directly (not via batch), just run the first symbol
    data = load_data(config.SYMBOLS[0])
    # Updated to $50 starting balance
    tester = CustomBacktester(data, starting_balance=50.0)
    tester.run()
    tester.generate_report()
