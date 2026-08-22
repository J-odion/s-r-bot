import os
import sys
import pandas as pd
from backtesting import Backtest, Strategy

# Adjust path so we can import from strategy
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config.settings as config
from strategy.sr_levels import detect_multi_timeframe_zones
from strategy.signal_engine import generate_signal

# This is a simplified backtest structure.
# In a real multi-timeframe backtest using `backtesting.py`,
# you often need to resample data or pass multiple arrays.

class SAndRStrategy(Strategy):
    def init(self):
        # We would pre-calculate zones here or dynamically on next()
        self.candidate_signal = None
        
    def next(self):
        # On every bar, check if a signal was generated.
        # This requires syncing the data_dict state up to self.data.index[-1]
        
        # Example structure:
        # data_dict = self.build_current_data_dict()
        # all_zones = detect_multi_timeframe_zones(data_dict, config)
        
        # if self.candidate_signal:
        #     # Check confirmation on this new candle
        #     confirmation_signal = generate_signal(data_dict, all_zones, config)
        #     if confirmation_signal and confirmation_signal["direction"] == self.candidate_signal["direction"]:
        #         if confirmation_signal["direction"] == "buy":
        #             self.buy(sl=confirmation_signal["sl_price"], tp=confirmation_signal["tp_price"])
        #         else:
        #             self.sell(sl=confirmation_signal["sl_price"], tp=confirmation_signal["tp_price"])
        #     self.candidate_signal = None
        # else:
        #     new_signal = generate_signal(data_dict, all_zones, config)
        #     if new_signal:
        #         self.candidate_signal = new_signal
        
        pass
        
        # Example structure:
        # data_dict = self.build_current_data_dict()
        # all_zones = detect_multi_timeframe_zones(data_dict, config)
        # signal = generate_signal(data_dict, all_zones, config)
        
        # if signal:
        #     if signal["direction"] == "buy":
        #         self.buy(sl=signal["sl_price"], tp=signal["tp_price"])
        #     else:
        #         self.sell(sl=signal["sl_price"], tp=signal["tp_price"])
        pass

def run_backtest(holdout_months=0):
    # 1. Load Data
    cache_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'cache')
    m5_file = os.path.join(cache_dir, f"{config.SYMBOL}_M5.csv")
    
    if not os.path.exists(m5_file):
        print(f"Data file {m5_file} not found. Please run fetch.py first.")
        return
        
    df_m5 = pd.read_csv(m5_file, parse_dates=['time'])
    df_m5.set_index('time', inplace=True)
    df_m5.rename(columns={'open': 'Open', 'high': 'High', 'low': 'Low', 'close': 'Close', 'tick_volume': 'Volume'}, inplace=True)
    
    # Train / Test split
    if holdout_months > 0:
        import datetime
        from dateutil.relativedelta import relativedelta
        split_date = df_m5.index[-1] - relativedelta(months=holdout_months)
        print(f"Splitting data at {split_date} for {holdout_months} holdout months.")
        # Only testing on the holdout (out of sample)
        # You could also test on the train set (df_m5.loc[:split_date])
        df_m5 = df_m5.loc[split_date:]
        
    # Calculate commission to simulate spread
    avg_price = df_m5['Close'].mean()
    # If spread is 30 points (e.g. 0.30 in price if XAUUSD), commission fraction is spread/price
    # Note: verify digit scaling for XAUUSDm on Exness. Assume 2 digits for points (0.01 = 1 point)
    spread_value = config.BACKTEST_SPREAD_POINTS * 0.01 
    commission_pct = spread_value / avg_price if avg_price > 0 else 0
    
    # Run backtest
    bt = Backtest(df_m5, SAndRStrategy, cash=10000, margin=1/100, commission=commission_pct, trade_on_close=True)
    stats = bt.run()
    print(stats)
    
    results_dir = os.path.join(os.path.dirname(__file__), 'results')
    os.makedirs(results_dir, exist_ok=True)
    bt.plot(filename=os.path.join(results_dir, 'backtest_plot.html'))

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--holdout-months", type=int, default=0, help="Months to hold out for out-of-sample testing")
    args = parser.parse_args()
    run_backtest(args.holdout_months)
