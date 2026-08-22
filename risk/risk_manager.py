import MetaTrader5 as mt5
from datetime import datetime
from .news_filter import is_news_blackout

class RiskManager:
    def __init__(self, config):
        self.config = config
        self.daily_pnl = 0.0
        self.last_pnl_date = None
        self.trading_halted = False
        
    def get_lot_size(self, symbol):
        """
        Dynamically queries the minimum volume for the symbol from the broker.
        """
        symbol_info = mt5.symbol_info(symbol)
        if symbol_info is None:
            print(f"Failed to get symbol info for {symbol}")
            return None
        return symbol_info.volume_min
        
    def check_daily_loss(self):
        """
        Checks if the daily loss limit has been hit.
        (In a live system, this should query closed positions for the current day)
        """
        today = datetime.now().date()
        if self.last_pnl_date != today:
            self.daily_pnl = 0.0
            self.last_pnl_date = today
            self.trading_halted = False
            
        if self.daily_pnl <= -self.config.DAILY_LOSS_LIMIT_USD:
            self.trading_halted = True
            
        return self.trading_halted
        
    def update_pnl(self, pnl):
        self.daily_pnl += pnl
        
    def can_trade(self, symbol):
        """
        Checks max concurrent positions, daily loss limits, and news blackout windows.
        """
        if self.check_daily_loss():
            print("Trading halted for the day due to max loss limit.")
            return False
            
        if is_news_blackout(datetime.now(), self.config):
            print("Trading blocked: News blackout window active.")
            return False
            
        positions = mt5.positions_get(symbol=symbol)
        if positions is None:
            print("Failed to get positions.")
            return False
            
        if len(positions) >= self.config.MAX_CONCURRENT_POSITIONS:
            print("Max concurrent positions reached.")
            return False
            
        return True
