import os
import sys
import pandas as pd
import time
from datetime import timedelta

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from backtest.custom_engine import CustomBacktester, load_data
import config.settings as config

def run_batch_backtests():
    start_time = time.time()
    
    all_ict_trades = []
    all_sr_trades = []
    all_scalp_trades = []
    
    print("==============================================")
    print("      MULTI-PAIR BATCH BACKTEST INITIALIZED")
    print("==============================================\n")
    
    for symbol in config.SYMBOLS:
        print(f"\n>>> PROCESSING SYMBOL: {symbol} <<<")
        data = load_data(symbol)
        
        if "M5" not in data:
            print(f"M5 data not found for {symbol}. Skipping.")
            continue
            
        df_m5 = data["M5"]
        total_candles = len(df_m5)
        
        if total_candles < 500:
            print(f"Not enough data for {symbol}. Skipping.")
            continue
            
        print(f"Total M5 candles available: {total_candles} (Approx {total_candles / (12 * 24 * 20):.1f} months)")
        
        batch_size = 10000
        num_batches = (total_candles // batch_size) + 1
        
        symbol_ict_trades = []
        symbol_sr_trades = []
        symbol_scalp_trades = []
        
        for batch_num in range(num_batches):
            start_idx = batch_num * batch_size
            end_idx = min(start_idx + batch_size, total_candles)
            
            if end_idx - start_idx < 500:
                continue
                
            print(f"\n--- BATCH {batch_num + 1}/{num_batches} ({symbol}: Candles {start_idx} to {end_idx}) ---")
            
            tester = CustomBacktester(data, starting_balance=50.0)
            
            def custom_run(self):
                df_m5 = self.data_dict["M5"]
                # Adjust spread dynamically if needed, 30 points = 3.0 pips
                spread = 30 / 100.0 if "XAU" in symbol else 0.00030
                if "JPY" in symbol:
                    spread = 0.030
                    
                sr_candidate_signal = None
                sr_candidate_time = None
                self.last_scalp_time = None
                
                for i in range(start_idx, end_idx):
                    current_time = df_m5.index[i]
                    current_row = df_m5.iloc[i]
                    current_close = current_row['close']
                    current_high = current_row['high']
                    current_low = current_row['low']
                    
                    if i < 200:
                        continue
                        
                    trailing_m5 = df_m5.iloc[i-200:i+1]
                    
                    # Calculate ATR for this candle
                    tr0 = abs(trailing_m5['high'] - trailing_m5['low'])
                    tr1 = abs(trailing_m5['high'] - trailing_m5['close'].shift(1))
                    tr2 = abs(trailing_m5['low'] - trailing_m5['close'].shift(1))
                    m5_atr = pd.concat([tr0, tr1, tr2], axis=1).max(axis=1).tail(14).mean()
                    if pd.isna(m5_atr) or m5_atr == 0:
                        m5_atr = spread * 3 # Fallback
                        
                    # Cache macro trend once an hour to save time
                    if i % 12 == 0:
                        from strategy.trend import get_regime_state
                        d1_df = self.data_dict.get("D1")
                        if d1_df is not None:
                            d1_slice = d1_df[d1_df.index <= current_time]
                            regime_info = get_regime_state(d1_slice, config)
                            self.cached_macro_trend = regime_info["bias"]
                            self.cached_regime = regime_info["regime"]
                        else:
                            self.cached_macro_trend = "neutral"
                            self.cached_regime = "ranging"
                                
                    macro_trend = getattr(self, 'cached_macro_trend', "neutral")
                    macro_regime = getattr(self, 'cached_regime', "ranging")
                    
                    # Manage ICT Active Trades
                    if self.active_ict_trade:
                        trade = self.active_ict_trade
                        if trade['direction'] == 'bullish':
                            if current_low <= trade['sl']:
                                trade['exit_price'] = trade['sl']
                                trade['profit'] = (trade['sl'] - trade['entry_price']) * 0.10
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

                    # Manage SR Active Trades (Phase 3: Partial Close + Trail)
                    if self.active_sr_trade:
                        t = self.active_sr_trade
                        initial_risk = abs(t['entry_price'] - t['initial_sl'])
                        if initial_risk == 0:
                            initial_risk = m5_atr
                            
                        if t['direction'] == 'bullish':
                            if t.get('partial_closed', False):
                                trail_sl = current_high - (1.5 * m5_atr)
                                if trail_sl > t['sl']:
                                    t['sl'] = trail_sl
                                    
                            if not t.get('partial_closed', False) and current_high >= t['entry_price'] + initial_risk:
                                partial = t.copy()
                                partial['exit_price'] = t['entry_price'] + initial_risk
                                partial['profit'] = initial_risk * 0.10 * 0.5 
                                self.sr_trades.append(partial)
                                
                                t['partial_closed'] = True
                                t['sl'] = t['entry_price']
                                
                            if current_low <= t['sl']:
                                t['exit_price'] = t['sl']
                                size = 0.5 if t.get('partial_closed', False) else 1.0
                                t['profit'] = (t['sl'] - t['entry_price']) * 0.10 * size
                                self.sr_trades.append(t)
                                self.active_sr_trade = None
                        else:
                            if t.get('partial_closed', False):
                                trail_sl = current_low + (1.5 * m5_atr)
                                if trail_sl < t['sl']:
                                    t['sl'] = trail_sl
                                    
                            if not t.get('partial_closed', False) and current_low <= t['entry_price'] - initial_risk:
                                partial = t.copy()
                                partial['exit_price'] = t['entry_price'] - initial_risk
                                partial['profit'] = initial_risk * 0.10 * 0.5
                                self.sr_trades.append(partial)
                                
                                t['partial_closed'] = True
                                t['sl'] = t['entry_price']
                                
                            if current_high >= t['sl']:
                                t['exit_price'] = t['sl']
                                size = 0.5 if t.get('partial_closed', False) else 1.0
                                t['profit'] = (t['entry_price'] - t['sl']) * 0.10 * size
                                self.sr_trades.append(t)
                                self.active_sr_trade = None

                    # Manage Scalps
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

                    # Open Scalp Trades (ATR Normalized & Spread Gated)
                    if self.active_sr_trade:
                        t = self.active_sr_trade
                        
                        can_scalp = True
                        if self.last_scalp_time:
                            time_since = (current_time - self.last_scalp_time).total_seconds()
                            if time_since < 30 * 60:
                                can_scalp = False
                                
                        aligned = (t['direction'] == macro_trend)
                            
                        if can_scalp and aligned:
                            in_profit = False
                            
                            profit_dist = 0.2 * m5_atr
                            
                            if t['direction'] == 'bullish' and current_close > t['entry_price'] + profit_dist:
                                in_profit = True
                            elif t['direction'] == 'bearish' and current_close < t['entry_price'] - profit_dist:
                                in_profit = True
                                
                            if in_profit:
                                scalp_dir = t['direction']
                                scalp_entry = current_close
                                
                                sl_dist = 0.4 * m5_atr
                                tp_dist = 0.8 * m5_atr
                                
                                # Cost-Awareness Gate: spread must be < 15% of stop distance
                                spread_cost = spread / sl_dist if sl_dist > 0 else 1.0
                                if spread_cost <= 0.15:
                                    if scalp_dir == 'bullish':
                                        scalp_sl = scalp_entry - sl_dist
                                        scalp_tp = scalp_entry + tp_dist
                                    else:
                                        scalp_sl = scalp_entry + sl_dist
                                        scalp_tp = scalp_entry - tp_dist
                                        
                                    parent_id = t.get('signal_id', f"sr_{t['time'].strftime('%m%d%H%M')}")
                                    self.active_scalps.append({
                                        'time': current_time,
                                        'direction': scalp_dir,
                                        'entry_price': scalp_entry,
                                        'sl': scalp_sl,
                                        'tp': scalp_tp,
                                        'parent_signal_id': parent_id
                                    })
                                    self.last_scalp_time = current_time

                    # ICT Engine Eval (Regime Gated to Trending, ATR Normalized)
                    if not self.active_ict_trade and macro_regime == "trending":
                        trailing_m5_with_time = trailing_m5.reset_index()
                        ict_signal, ict_reason, ict_entry = self.ict_engine.evaluate(trailing_m5_with_time, macro_trend=macro_trend)
                        if ict_signal != 0:
                            dir_str = "bullish" if ict_signal == 1 else "bearish"
                            
                            sl_dist = 0.5 * m5_atr
                            tp_dist = 5.0 * m5_atr
                            
                            # Cost-Awareness Gate
                            spread_cost = spread / sl_dist if sl_dist > 0 else 1.0
                            if spread_cost <= 0.15:
                                sl = current_low - sl_dist if ict_signal == 1 else current_high + sl_dist
                                tp = current_close + tp_dist if ict_signal == 1 else current_close - tp_dist
                                entry_price = current_close + spread if ict_signal == 1 else current_close - spread
                                
                                self.active_ict_trade = {
                                    'time': current_time,
                                    'direction': dir_str,
                                    'entry_price': entry_price,
                                    'sl': sl,
                                    'tp': tp,
                                    'parent_signal_id': f"ict_{current_time.strftime('%m%d%H%M')}"
                                }

                    # S/R Engine Eval (Regime Gated to Ranging)
                    if macro_regime != "ranging":
                        sr_candidate_signal = None
                        sr_candidate_time = None
                    else:
                        if i % 12 == 0:
                            sliced_dict = {}
                            from strategy.sr_levels import detect_multi_timeframe_zones
                            for tf, df in self.data_dict.items():
                                sliced_df = df[df.index <= current_time]
                                if len(sliced_df) > 0:
                                    sliced_dict[tf] = sliced_df.tail(200).reset_index()
                            self.cached_zones = detect_multi_timeframe_zones(sliced_dict, config)
                            self.cached_sliced_dict = sliced_dict
                        
                        if not self.active_sr_trade and hasattr(self, 'cached_zones'):
                            from strategy.signal_engine import generate_signal
                            current_m5_slice = trailing_m5.reset_index()
                            eval_dict = self.cached_sliced_dict.copy()
                            eval_dict["M5"] = current_m5_slice
                            
                            if sr_candidate_signal and current_time > sr_candidate_time:
                                conf_signal = generate_signal(eval_dict, self.cached_zones, config)
                                if conf_signal and conf_signal["direction"] == sr_candidate_signal["direction"]:
                                    dir_str = 'bullish' if conf_signal["direction"] == "buy" else 'bearish'
                                    entry_price = current_close + spread if dir_str == 'bullish' else current_close - spread
                                    
                                    sl_dist = abs(entry_price - conf_signal["sl_price"])
                                    spread_cost = spread / sl_dist if sl_dist > 0 else 1.0
                                    
                                    if spread_cost <= 0.15:
                                        self.active_sr_trade = {
                                            'time': current_time,
                                            'direction': dir_str,
                                            'entry_price': entry_price,
                                            'sl': conf_signal["sl_price"],
                                            'initial_sl': conf_signal["sl_price"],
                                            'tp': conf_signal["tp_price"],
                                            'partial_closed': False,
                                            'signal_id': f"sr_{current_time.strftime('%m%d%H%M')}_{round(entry_price, 3)}"
                                        }
                                sr_candidate_signal = None
                                sr_candidate_time = None
                            elif not sr_candidate_signal:
                                new_signal = generate_signal(eval_dict, self.cached_zones, config)
                                if new_signal:
                                    sr_candidate_signal = new_signal
                                    sr_candidate_time = current_time

            import types
            tester.run = types.MethodType(custom_run, tester)
            tester.run()
            
            symbol_ict_trades.extend(tester.ict_trades)
            symbol_sr_trades.extend(tester.sr_trades)
            symbol_scalp_trades.extend(tester.scalp_trades)
            
        # We will NOT write a file per-symbol anymore. We will use the massive AdvancedReporter
        # to generate ONE master report at the end that breaks everything down.
        all_ict_trades.extend(symbol_ict_trades)
        all_sr_trades.extend(symbol_sr_trades)
        all_scalp_trades.extend(symbol_scalp_trades)
            
    # Final Reporting using the AdvancedReporter
    end_time = time.time()
    elapsed = str(timedelta(seconds=int(end_time - start_time)))
    
    from backtest.reporter import AdvancedReporter
    
    reports_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data', 'reports')
    reporter = AdvancedReporter(reports_dir)
    
    metadata = {
        "symbols": config.SYMBOLS
    }
    
    report_path = reporter.generate_master_report(all_ict_trades, all_sr_trades, all_scalp_trades, metadata)
    
    # Also print the executive summary to the terminal
    total_trades = len(all_ict_trades) + len(all_sr_trades) + len(all_scalp_trades)
    total_profit = sum(t['profit'] for t in (all_ict_trades + all_sr_trades + all_scalp_trades))
    
    print("\n\n=======================================================")
    print("                 MASTER AGGREGATED REPORT")
    print("=======================================================\n")
    print(f" TOTAL TRADES ACROSS ALL PAIRS: {total_trades}")
    print(f" GRAND TOTAL NET PROFIT:        ${total_profit:.2f}")
    print(f" TOTAL EXECUTION TIME:          {elapsed}")
    print(f" MASTER REPORT SAVED TO:        {report_path}")
    print("=======================================================\n")
    
    if total_trades > 0:
        # Print a tiny snapshot to terminal
        with open(report_path, 'r') as f:
            lines = f.readlines()
            # Print sections 2 and 3
            start_print = False
            for line in lines:
                if "2. EXECUTIVE SUMMARY" in line:
                    start_print = True
                if "4. RISK METRICS" in line:
                    break
                if start_print:
                    print(line.rstrip())


if __name__ == "__main__":
    run_batch_backtests()
