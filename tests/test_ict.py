import pytest
import pandas as pd
from datetime import datetime, time
from strategy.ict_engine import ICTEngine

def test_ict_killzone():
    engine = ICTEngine()
    
    # London Killzone (9:00 - 12:00 Server Time)
    t1 = datetime(2026, 9, 5, 10, 0)
    assert engine.in_killzone(t1) == True
    
    # Outside Killzone
    t2 = datetime(2026, 9, 5, 13, 0)
    assert engine.in_killzone(t2) == False
    
    # NY Killzone (15:00 - 18:00 Server Time)
    t3 = datetime(2026, 9, 5, 16, 30)
    assert engine.in_killzone(t3) == True

def test_ict_fvg():
    engine = ICTEngine()
    
    # Bullish FVG
    df_bull = pd.DataFrame({
        'high': [100, 105, 110],
        'low': [90, 95, 102],
        'close': [95, 104, 109]
    })
    assert engine.detect_fvg(df_bull) == 'bullish'
    
    # Bearish FVG
    df_bear = pd.DataFrame({
        'high': [110, 105, 100],
        'low': [102, 95, 90],
        'close': [103, 96, 91]
    })
    assert engine.detect_fvg(df_bear) == 'bearish'

    # No FVG (Overlap)
    df_no = pd.DataFrame({
        'high': [100, 105, 110],
        'low': [90, 95, 98],
        'close': [95, 104, 109]
    })
    assert engine.detect_fvg(df_no) == None
