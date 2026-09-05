import pandas as pd
from datetime import datetime, time
import logging

logger = logging.getLogger(__name__)

class ICTEngine:
    def __init__(self, killzones=None):
        """
        Killzones: list of dicts with 'start' and 'end' time objects.
        Default NY and London killzones for GMT/Server time.
        """
        if killzones is None:
            # Assuming broker time is roughly GMT+2/3, adjust as needed
            self.killzones = [
                {"name": "London", "start": time(9, 0), "end": time(12, 0)}, # 2am-5am EST in GMT+2 = 9am-12pm
                {"name": "New York", "start": time(15, 0), "end": time(18, 0)} # 8am-11am EST in GMT+2 = 15:00-18:00
            ]
        else:
            self.killzones = killzones

    def in_killzone(self, current_time: datetime) -> bool:
        """Check if current time is within an active killzone."""
        c_time = current_time.time()
        for kz in self.killzones:
            if kz['start'] <= c_time <= kz['end']:
                return True
        return False

    def detect_sweep(self, df, lookback=20):
        """
        Detects if the most recent price action swept a significant high or low.
        Returns: 'bullish' (swept low), 'bearish' (swept high), or None.
        """
        if len(df) < lookback:
            return None
            
        recent = df.tail(lookback)
        current = df.iloc[-1]
        
        # Define significant swing high/low in the lookback window (excluding current candle)
        window = df.iloc[-lookback:-1]
        swing_high = window['high'].max()
        swing_low = window['low'].min()
        
        # Bullish sweep: Current candle dipped below swing low but closed above it
        if current['low'] < swing_low and current['close'] > swing_low:
            return 'bullish'
            
        # Bearish sweep: Current candle spiked above swing high but closed below it
        if current['high'] > swing_high and current['close'] < swing_high:
            return 'bearish'
            
        return None

    def detect_fvg(self, df):
        """
        Detects Fair Value Gaps in the last 3 candles.
        Returns 'bullish', 'bearish', or None.
        """
        if len(df) < 3:
            return None
            
        c1 = df.iloc[-3]
        c3 = df.iloc[-1]
        
        # Bullish FVG: c1 high is strictly lower than c3 low
        if c1['high'] < c3['low']:
            return 'bullish'
            
        # Bearish FVG: c1 low is strictly higher than c3 high
        if c1['low'] > c3['high']:
            return 'bearish'
            
        return None

    def evaluate(self, df):
        """
        Evaluates the current dataframe (M5 or M15) for a complete ICT setup.
        Returns:
            - signal: 1 (Buy), -1 (Sell), or 0 (None)
            - reason: String explanation
            - fvg_level: The entry level to place a limit order
        """
        current_time = df.index[-1] if isinstance(df.index, pd.DatetimeIndex) else datetime.now()
        
        # 1. Time Check
        if not self.in_killzone(current_time):
            return 0, "Outside Killzone", None
            
        # 2. Liquidity Sweep Check
        sweep = self.detect_sweep(df)
        if not sweep:
            return 0, "No Sweep", None
            
        # 3. FVG / MSS Check
        fvg = self.detect_fvg(df)
        if not fvg:
            return 0, "No FVG", None
            
        # Alignment
        if sweep == 'bullish' and fvg == 'bullish':
            entry_level = df.iloc[-1]['low'] # Top of the bullish FVG is c3's low (roughly)
            return 1, "ICT Bullish Sweep + FVG", entry_level
            
        if sweep == 'bearish' and fvg == 'bearish':
            entry_level = df.iloc[-1]['high'] # Bottom of bearish FVG is c3's high
            return -1, "ICT Bearish Sweep + FVG", entry_level
            
        return 0, "No Alignment", None
