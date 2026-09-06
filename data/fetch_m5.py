import MetaTrader5 as mt5
import pandas as pd
from datetime import datetime

mt5.initialize(path=r'C:\Program Files\MetaTrader 5\terminal64.exe')
mt5.login(112212030, 'Yz!zAk4d', 'MetaQuotes-Demo')

rates = mt5.copy_rates_from_pos('XAUUSD', mt5.TIMEFRAME_M5, 0, 100000)
if rates is None:
    print(f"Failed 100k, trying 50k... Error: {mt5.last_error()}")
    rates = mt5.copy_rates_from_pos('XAUUSD', mt5.TIMEFRAME_M5, 0, 50000)

if rates is not None:
    print(f"Fetched {len(rates)} M5 bars")
    df = pd.DataFrame(rates)
    df['time'] = pd.to_datetime(df['time'], unit='s')
    df.to_csv('data/cache/XAUUSD_M5.csv', index=False)
else:
    print("Failed to fetch M5 data completely:", mt5.last_error())

mt5.shutdown()
