import os
import argparse
import pandas as pd
import MetaTrader5 as mt5
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

TIMEFRAME_MAP = {
    "M1": mt5.TIMEFRAME_M1,
    "M5": mt5.TIMEFRAME_M5,
    "M15": mt5.TIMEFRAME_M15,
    "H1": mt5.TIMEFRAME_H1,
    "H4": mt5.TIMEFRAME_H4,
    "D1": mt5.TIMEFRAME_D1,
    "W1": mt5.TIMEFRAME_W1,
    "MN1": mt5.TIMEFRAME_MN1,
}

def connect_mt5():
    """Initializes and connects to the MT5 terminal."""
    if not mt5.initialize():
        print("Standard initialize() failed, trying specific path...")
        if not mt5.initialize(path=r"C:\Program Files\MetaTrader 5\terminal64.exe"):
            print(f"initialize() failed, error code = {mt5.last_error()}")
            return False
    
    login = os.getenv("MT5_LOGIN")
    password = os.getenv("MT5_PASSWORD")
    server = os.getenv("MT5_SERVER")

    if login and password and server:
        authorized = mt5.login(int(login), password=password, server=server)
        if not authorized:
            print(f"failed to connect at account #{login}, error code: {mt5.last_error()}")
            return False
        else:
            print(f"Connected to account #{login} on {server}")
    else:
        print("No explicit MT5 credentials found in .env, proceeding with current terminal session.")
    
    return True

def fetch_data(symbol, timeframe_str, years_back):
    """Fetches historical OHLCV data from MT5 and saves to CSV."""
    if timeframe_str not in TIMEFRAME_MAP:
        print(f"Unsupported timeframe: {timeframe_str}")
        return

    tf = TIMEFRAME_MAP[timeframe_str]
    
    # Calculate datetime range
    date_to = datetime.now()
    date_from = date_to - timedelta(days=365 * years_back)
    
    print(f"Fetching {symbol} {timeframe_str} from {date_from.strftime('%Y-%m-%d')} to {date_to.strftime('%Y-%m-%d')}")
    
    rates = mt5.copy_rates_range(symbol, tf, date_from, date_to)
    
    if rates is None or len(rates) == 0:
        print(f"Failed to fetch rates for {symbol} {timeframe_str}, error: {mt5.last_error()}")
        return
        
    df = pd.DataFrame(rates)
    df['time'] = pd.to_datetime(df['time'], unit='s')
    
    # Cache to file
    cache_dir = os.path.join(os.path.dirname(__file__), 'cache')
    os.makedirs(cache_dir, exist_ok=True)
    file_path = os.path.join(cache_dir, f"{symbol}_{timeframe_str}.csv")
    df.to_csv(file_path, index=False)
    print(f"Saved {len(df)} rows to {file_path}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Fetch historical data from MT5")
    parser.add_argument("--symbol", type=str, default="XAUUSDm", help="Symbol to fetch (e.g., XAUUSDm)")
    parser.add_argument("--timeframes", type=str, default="M5,D1,W1,MN1", help="Comma-separated timeframes (e.g., M5,D1,W1)")
    parser.add_argument("--years", type=float, default=3.0, help="Years of history to fetch")
    
    args = parser.parse_args()
    
    if connect_mt5():
        timeframes = [tf.strip() for tf in args.timeframes.split(',')]
        for tf in timeframes:
            fetch_data(args.symbol, tf, args.years)
        mt5.shutdown()
