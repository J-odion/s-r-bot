import MetaTrader5 as mt5

class MT5Executor:
    def __init__(self, symbol, risk_manager):
        self.symbol = symbol
        self.risk_manager = risk_manager
        
    def execute_signal(self, signal):
        """
        Takes a signal dict and sends the order to MT5.
        """
        if not self.risk_manager.can_trade(self.symbol):
            return False
            
        lot_size = self.risk_manager.get_lot_size(self.symbol)
        if lot_size is None:
            return False
            
        order_type = mt5.ORDER_TYPE_BUY if signal["direction"] == "buy" else mt5.ORDER_TYPE_SELL
        price = mt5.symbol_info_tick(self.symbol).ask if order_type == mt5.ORDER_TYPE_BUY else mt5.symbol_info_tick(self.symbol).bid
        
        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": self.symbol,
            "volume": lot_size,
            "type": order_type,
            "price": price,
            "sl": signal["sl_price"],
            "deviation": 20,
            "magic": 234000,
            "comment": f"S/R Bot {signal['zone_timeframe']}",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }
        
        if signal.get("tp_price"):
            request["tp"] = signal["tp_price"]
            
        result = mt5.order_send(request)
        
        if result.retcode != mt5.TRADE_RETCODE_DONE:
            print(f"Order failed, retcode={result.retcode}")
            return False
            
        print(f"Order filled: ticket={result.order}, price={result.price}, sl={signal['sl_price']}, tp={signal.get('tp_price')}")
        return True

    def close_all_positions(self, fallback_sl_to_breakeven=True):
        """
        Closes all open positions for the symbol. 
        If it fails, retries once. If it still fails, tightens SL to breakeven + buffer as a fallback.
        """
        positions = mt5.positions_get(symbol=self.symbol)
        if not positions:
            return True
            
        success = True
        for pos in positions:
            order_type = mt5.ORDER_TYPE_SELL if pos.type == mt5.ORDER_TYPE_BUY else mt5.ORDER_TYPE_BUY
            price = mt5.symbol_info_tick(self.symbol).bid if order_type == mt5.ORDER_TYPE_SELL else mt5.symbol_info_tick(self.symbol).ask
            
            request = {
                "action": mt5.TRADE_ACTION_DEAL,
                "position": pos.ticket,
                "symbol": self.symbol,
                "volume": pos.volume,
                "type": order_type,
                "price": price,
                "deviation": 20,
                "magic": 234000,
                "comment": "Pre-news close",
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": mt5.ORDER_FILLING_IOC,
            }
            
            result = mt5.order_send(request)
            if result.retcode != mt5.TRADE_RETCODE_DONE:
                print(f"Failed to close position {pos.ticket}. Retrying once...")
                # Retry once
                result = mt5.order_send(request)
                if result.retcode != mt5.TRADE_RETCODE_DONE:
                    print(f"Retry failed to close position {pos.ticket}. Error: {result.retcode}")
                    success = False
                    if fallback_sl_to_breakeven:
                        # Fallback: move SL to breakeven + buffer (for spread widening)
                        # We use the wider buffer from settings explicitly meant for this scenario
                        wider_buffer = config.NEWS_FALLBACK_SL_BUFFER_POINTS
                        sl_price = pos.price_open + wider_buffer if pos.type == mt5.ORDER_TYPE_BUY else pos.price_open - wider_buffer
                        modify_req = {
                            "action": mt5.TRADE_ACTION_SLTP,
                            "position": pos.ticket,
                            "symbol": self.symbol,
                            "sl": sl_price,
                            "tp": pos.tp
                        }
                        mt5.order_send(modify_req)
                        print(f"Fallback applied: Moved SL to {sl_price} for position {pos.ticket}")
                else:
                    print(f"Successfully closed position {pos.ticket} on retry.")
            else:
                print(f"Successfully closed position {pos.ticket}.")
                
        return success
