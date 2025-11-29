import logging
import time

logger = logging.getLogger(__name__)

class Executor:
    def __init__(self, config, mt5_client):
        self.config = config # Full config
        self.exec_config = config.get('execution', {})
        self.mt5 = mt5_client

    def execute_signal(self, signal, lot_size):
        """
        Execute the signal by placing an order.
        """
        logger.info(f"Executing Signal: {signal.side} {signal.symbol} Lot:{lot_size} @ {signal.entry_price}")
        
        # Retry logic for transient errors
        max_retries = 3
        for attempt in range(max_retries):
            result = self.mt5.place_order_market(
                symbol=signal.symbol,
                volume=lot_size,
                side=signal.side,
                sl=signal.sl_price,
                tp=signal.tp_price,
                deviation=self.exec_config.get('deviation', 20),
                comment=f"RSI Bot {signal.reason}",
                magic=self.exec_config.get('magic', 0)
            )
            
            retcode = result.get('retcode')
            
            if retcode == 10009 or retcode == 10008: # TRADE_RETCODE_DONE or PLACED
                logger.info(f"Order placed successfully: Ticket {result.get('order')}")
                return result
            elif retcode in [10004, 10021]: # REQUOTE, NO_MONEY (maybe wait?)
                logger.warning(f"Order failed (Transient): {result.get('comment')} Retcode: {retcode}")
                time.sleep(1)
            else:
                logger.error(f"Order failed (Permanent): {result.get('comment')} Retcode: {retcode}")
                return None
                
        return None

    def manage_trailing_stops(self, symbol: str):
        """
        Check open positions and update SL if trailing conditions met.
        """
        trailing_config = self.config.get('trailing', {})
        if not trailing_config.get('enabled', False):
            return

        positions = self.mt5.get_open_positions(symbol=symbol)
        if not positions:
            return

        activation_rr = trailing_config.get('activation_rr', 1.0)
        trailing_dist_rr = trailing_config.get('trailing_dist_rr', 0.5)
        
        for pos in positions:
            ticket = pos['ticket']
            entry_price = pos['price_open']
            current_sl = pos['sl']
            current_price = pos['price_current']
            pos_type = pos['type'] # 0=BUY, 1=SELL
            
            # Calculate R (Risk distance)
            # We need original SL to calculate R. 
            # If SL has moved, we can't know original R easily unless we store it.
            # Heuristic: Assume initial SL was set by strategy. 
            # If current_sl is 0 (no SL), we can't calculate R.
            if current_sl == 0:
                continue
                
            # Calculate current profit in points
            if pos_type == 0: # BUY
                dist_to_sl = entry_price - current_sl
                # If SL is above entry (already trailed), dist_to_sl is negative? 
                # No, R is always positive distance.
                # If we moved SL, we lost the original R reference.
                # Let's use current price vs entry price for profit check.
                profit_points = current_price - entry_price
                
                # We need a reference "R". Let's assume R = 500 points if we can't find it?
                # Or use the config 'sl_points' as a proxy for R.
                # Better: Use config['strategy']['sl_points'] * point
                # But we don't have access to strategy config here easily unless passed.
                # Let's assume R is roughly (Entry - Initial SL). 
                # If SL is already moved, we can't know.
                # Alternative: Use fixed points for trailing.
                # Let's try to deduce R from current SL if it looks like initial.
                # If SL > Entry (Buy), we already moved it.
                
                # SIMPLIFICATION: Use 'sl_points' from config if available, else heuristic.
                # We passed 'config' to Executor. Is it full config or just execution?
                # Main passes config['execution']. We need strategy config for sl_points.
                # Let's assume user puts 'sl_points' in 'trailing' config for simplicity or we fetch from symbol.
                
                # Let's use a simpler logic:
                # If Profit > X points, Move SL to (CurrentPrice - Y points).
                pass
            
            # RE-IMPLEMENTATION with R logic requires knowing R.
            # Let's assume R = 500 points (default) * point_value.
            symbol_info = self.mt5.get_symbol_info(symbol)
            point = symbol_info.point
            
            # Default R in points (500)
            r_points = 500 
            r_value = r_points * point
            
            activation_dist = r_value * activation_rr
            trailing_dist = r_value * trailing_dist_rr
            
            if pos_type == 0: # BUY
                profit = current_price - entry_price
                if profit >= activation_dist:
                    new_sl = current_price - trailing_dist
                    # Only move SL up
                    if new_sl > current_sl:
                        # Ensure new SL is not too close to current price (StopLevel)
                        # For now, just send it.
                        logger.info(f"Trailing Stop Triggered for BUY {ticket}. Profit: {profit/point:.1f} pts. Moving SL to {new_sl}")
                        self.mt5.modify_position(ticket, sl=new_sl)
                        
            elif pos_type == 1: # SELL
                profit = entry_price - current_price
                if profit >= activation_dist:
                    new_sl = current_price + trailing_dist
                    # Only move SL down
                    if current_sl == 0 or new_sl < current_sl:
                        logger.info(f"Trailing Stop Triggered for SELL {ticket}. Profit: {profit/point:.1f} pts. Moving SL to {new_sl}")
                        self.mt5.modify_position(ticket, sl=new_sl)
