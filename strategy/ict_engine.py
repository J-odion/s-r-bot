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
                {"name": "London", "start": time(8, 0), "end": time(12, 0)},
                {"name": "New York", "start": time(13, 0), "end": time(18, 0)}
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
        
    def calculate_atr(self, df, period=14):
        """Calculate the current ATR value using the last `period` candles."""
        if len(df) < period + 1:
            return 0
        window = df.tail(period + 1).copy()
        tr0 = abs(window['high'] - window['low'])
        tr1 = abs(window['high'] - window['close'].shift(1))
        tr2 = abs(window['low'] - window['close'].shift(1))
        tr = pd.concat([tr0, tr1, tr2], axis=1).max(axis=1)
        return tr.mean()

    def detect_sweep(self, df, atr, lookback=20, min_depth_fraction=0.1):
        """
        Detects if the most recent price action swept a significant high or low.
        Requires the sweep depth (wick beyond swing) to be at least min_depth_fraction * ATR.
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
        
        # Required depth
        min_depth = atr * min_depth_fraction
        
        # Bullish sweep: Current candle dipped below swing low significantly but closed above it
        if current['low'] < swing_low - min_depth and current['close'] > swing_low:
            return 'bullish'
            
        # Bearish sweep: Current candle spiked above swing high significantly but closed below it
        if current['high'] > swing_high + min_depth and current['close'] < swing_high:
            return 'bearish'
            
        return None

    def detect_fvg(self, df, atr, lookback=5, min_size_fraction=0.3):
        """
        Detects Fair Value Gaps in the last `lookback` candles.
        Requires the FVG gap size to be > min_size_fraction * ATR.
        Returns 'bullish', 'bearish', or None.
        """
        if len(df) < lookback:
            return None
            
        min_size = atr * min_size_fraction
            
        # Check all 3-candle windows in the lookback period
        for i in range(len(df) - lookback, len(df) - 2):
            c1 = df.iloc[i]
            c3 = df.iloc[i+2]
            
            # Bullish FVG: c1 high is strictly lower than c3 low
            if c1['high'] < c3['low']:
                gap_size = c3['low'] - c1['high']
                if gap_size > min_size:
                    return 'bullish'
                
            # Bearish FVG: c1 low is strictly higher than c3 high
            if c1['low'] > c3['high']:
                gap_size = c1['low'] - c3['high']
                if gap_size > min_size:
                    return 'bearish'
                
        return None

    def evaluate(self, df, macro_trend=None):
        """
        Evaluates the current dataframe (M5 or M15) for a complete ICT setup.
        Accepts macro_trend ("bullish", "bearish", or "conflicted") to filter trades.
        Returns:
            - signal: 1 (Buy), -1 (Sell), or 0 (None)
            - reason: String explanation
            - fvg_level: The entry level to place a limit order
        """
        if 'time' in df.columns:
            current_time = df.iloc[-1]['time']
        elif isinstance(df.index, pd.DatetimeIndex):
            current_time = df.index[-1]
        else:
            current_time = datetime.now()
        
        # 1. Time Check
        if not self.in_killzone(current_time):
            return 0, "Outside Killzone", None
            
        # Calculate ATR
        atr = self.calculate_atr(df)
        if atr == 0:
            return 0, "Not enough data for ATR", None
            
        # 2. Liquidity Sweep Check
        sweep = self.detect_sweep(df, atr, lookback=10, min_depth_fraction=0.1)
        if not sweep:
            return 0, "No Valid Sweep", None
            
        # 3. FVG / MSS Check
        fvg = self.detect_fvg(df, atr, min_size_fraction=0.3)
        if not fvg:
            return 0, "No Valid FVG", None
            
        # Alignment & Macro Trend Filter
        if sweep == 'bullish' and fvg == 'bullish':
            if macro_trend and macro_trend != 'bullish':
                return 0, "Counter to Macro Trend", None
            entry_level = df.iloc[-1]['low'] # Top of the bullish FVG is c3's low (roughly)
            return 1, "ICT Bullish Sweep + FVG", entry_level
            
        if sweep == 'bearish' and fvg == 'bearish':
            if macro_trend and macro_trend != 'bearish':
                return 0, "Counter to Macro Trend", None
            entry_level = df.iloc[-1]['high'] # Bottom of bearish FVG is c3's high
            return -1, "ICT Bearish Sweep + FVG", entry_level
            
        return 0, "No Alignment", None
