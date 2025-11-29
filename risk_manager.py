import logging
import math

logger = logging.getLogger(__name__)

class RiskManager:
    def __init__(self, config, mt5_client):
        self.config = config
        self.mt5 = mt5_client
        self.daily_loss = 0.0
        self.consecutive_losses = 0
        self.halt_trading = False

    def check_safety(self, account_balance):
        """
        Check circuit breakers (daily loss, consecutive losses).
        """
        if self.halt_trading:
            return False
            
        if account_balance <= 0:
            logger.warning(f"Account balance is {account_balance}. Halting trading.")
            self.halt_trading = True
            return False

        max_daily_loss = account_balance * (self.config['max_daily_loss_percent'] / 100.0)
        if self.daily_loss >= max_daily_loss:
            logger.warning(f"Max daily loss reached ({self.daily_loss} >= {max_daily_loss}). Halting trading.")
            self.halt_trading = True
            return False
            
        if self.consecutive_losses >= self.config['max_consecutive_losses']:
            logger.warning(f"Max consecutive losses reached ({self.consecutive_losses}). Halting trading.")
            self.halt_trading = True
            return False
            
        return True

    def compute_lot_size(self, symbol: str, sl_price: float, entry_price: float, account_balance: float) -> float:
        """
        Compute lot size based on risk percentage and Stop Loss distance.
        """
        if not self.check_safety(account_balance):
            return 0.0

        risk_amount = account_balance * (self.config['risk_percent_per_trade'] / 100.0)
        
        # Get symbol properties
        symbol_info = self.mt5.get_symbol_info(symbol)
        if symbol_info is None:
            logger.error(f"Could not get symbol info for {symbol}")
            return 0.0
            
        # Calculate SL distance in points
        # point = symbol_info.point
        # sl_points = abs(entry_price - sl_price) / point
        
        # Calculate Tick Value and Tick Size to determine value per point
        # Profit = (Close - Open) * ContractSize (for Forex/Metals usually)
        # More accurately: DeltaPrice / TickSize * TickValue
        
        price_diff = abs(entry_price - sl_price)
        if price_diff == 0:
            return 0.0
            
        tick_size = symbol_info.trade_tick_size
        tick_value = symbol_info.trade_tick_value
        
        if tick_size == 0:
             logger.error("Tick size is 0")
             return 0.0
             
        # Loss per 1.0 lot if SL is hit
        loss_per_lot = (price_diff / tick_size) * tick_value
        
        if loss_per_lot == 0:
            return 0.0
            
        lot_size = risk_amount / loss_per_lot
        
        # Normalize lot size
        lot_step = symbol_info.volume_step
        lot_min = symbol_info.volume_min
        lot_max = symbol_info.volume_max
        
        # Round down to nearest step
        lot_size = math.floor(lot_size / lot_step) * lot_step
        
        if lot_size < lot_min:
            logger.warning(f"Calculated lot {lot_size} < min {lot_min}. Skipping.")
            return 0.0
            
        if lot_size > lot_max:
            lot_size = lot_max
            
        return round(lot_size, 2)

    def update_metrics(self, profit: float):
        """
        Update daily loss and consecutive loss counters based on closed trade profit.
        """
        if profit < 0:
            self.daily_loss += abs(profit)
            self.consecutive_losses += 1
        else:
            # Optional: Reduce daily loss by profit? Or just track gross loss?
            # Usually daily loss limit is about "how much I lost today", net or gross.
            # Let's assume Net P&L for the day.
            self.daily_loss -= profit 
            if self.daily_loss < 0:
                self.daily_loss = 0
            self.consecutive_losses = 0
