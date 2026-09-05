import logging

logger = logging.getLogger(__name__)

class ScalpManager:
    def __init__(self, mt5_executor, profit_trigger_pips=20, scalp_sl_pips=10, scalp_tp_pips=30, max_scalps=3):
        self.mt5 = mt5_executor
        self.profit_trigger_points = profit_trigger_pips * 10 # 1 pip = 10 points usually
        self.scalp_sl_points = scalp_sl_pips * 10
        self.scalp_tp_points = scalp_tp_pips * 10
        self.max_scalps = max_scalps
        self.active_scalps = {} # Mapping parent_ticket to number of active scalps

    def manage_scalps(self, current_price, current_positions):
        """
        Monitors active positions. If a main position reaches the profit trigger,
        opens a scalp trade in the same direction.
        """
        for pos in current_positions:
            # We only want to scalp off of main positions, assuming scalps have a specific magic number
            # Let's assume magic_number for S/R is 1001, ICT is 1002, Scalps are 2000
            if pos.get('magic', 0) >= 2000:
                continue
                
            ticket = pos['ticket']
            entry = pos['price_open']
            direction = pos['type'] # 0 for BUY, 1 for SELL (MT5 constants usually)
            
            pnl_points = 0
            if direction == 0: # BUY
                pnl_points = (current_price['bid'] - entry) / self.mt5.get_point()
            elif direction == 1: # SELL
                pnl_points = (entry - current_price['ask']) / self.mt5.get_point()
                
            if pnl_points >= self.profit_trigger_points:
                current_scalps = self.active_scalps.get(ticket, 0)
                if current_scalps < self.max_scalps:
                    logger.info(f"Main position {ticket} is in profit (+{pnl_points} pts). Triggering scalp {current_scalps+1}/{self.max_scalps}")
                    self._execute_scalp(direction, current_price, ticket)
                    self.active_scalps[ticket] = current_scalps + 1

    def _execute_scalp(self, direction, current_price, parent_ticket):
        """
        Executes a market order for a scalp with strict SL/TP.
        """
        symbol = self.mt5.symbol
        point = self.mt5.get_point()
        
        # Calculate SL/TP
        if direction == 0: # BUY
            price = current_price['ask']
            sl = price - (self.scalp_sl_points * point)
            tp = price + (self.scalp_tp_points * point)
            # 0 is usually ORDER_TYPE_BUY
            order_type = 0 
        else:
            price = current_price['bid']
            sl = price + (self.scalp_sl_points * point)
            tp = price - (self.scalp_tp_points * point)
            # 1 is usually ORDER_TYPE_SELL
            order_type = 1
            
        # Send order via mt5_executor
        result = self.mt5.execute_market_order(
            symbol=symbol,
            order_type=order_type,
            volume=0.01, # Default minimum volume for scalp
            price=price,
            sl=sl,
            tp=tp,
            magic=2000 + parent_ticket % 1000, # Unique magic for scalps associated with parent
            comment="Scalp Trigger"
        )
        
        if result:
            logger.info(f"Scalp executed successfully for parent {parent_ticket}")
        else:
            logger.error(f"Failed to execute scalp for parent {parent_ticket}")

    def reset(self):
        """Clear tracking, useful when all positions close."""
        self.active_scalps.clear()
