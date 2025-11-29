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

    def sync_daily_stats(self):
        """
        Sync daily loss and consecutive losses from MT5 history.
        """
        from datetime import datetime, timedelta
        
        now = datetime.now()
        # Start of day (00:00:00)
        from_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
        
        deals = self.mt5.get_history_deals(from_date, now)
        
        daily_profit = 0.0
        consecutive_losses = 0
        
        # Sort deals by time to count consecutive losses correctly
        # Assuming get_history_deals returns list of dicts, we need to sort if not sorted.
        # MT5 usually returns sorted by time, but let's be safe if we can, 
        # or just iterate.
        
        for deal in deals:
            profit = deal.get('profit', 0.0)
            swap = deal.get('swap', 0.0)
            commission = deal.get('commission', 0.0)
            net_profit = profit + swap + commission
            
            # Filter out non-trading deals (balance ops) if needed.
            # Usually entry=IN has 0 profit. entry=OUT has profit.
            # We only care about realized P&L.
            if net_profit == 0:
                continue
                
            daily_profit += net_profit
            
            if net_profit < 0:
                consecutive_losses += 1
            else:
                consecutive_losses = 0
                
        # If daily_profit is negative, that's our daily loss (positive number)
        if daily_profit < 0:
            self.daily_loss = abs(daily_profit)
        else:
            self.daily_loss = 0.0
            
        self.consecutive_losses = consecutive_losses
        
        logger.info(f"Risk State Synced: Daily Loss={self.daily_loss}, Consec Losses={self.consecutive_losses}")

    def check_safety(self, account_balance):
        """
        Check circuit breakers (daily loss, consecutive losses).
        """
        # Always sync before checking? Or rely on periodic sync?
        # For safety, let's trust the internal state which should be kept up to date.
        # But if we want to be super safe, we could sync here. 
        # For performance, let's assume sync is called in main loop.
        
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
        # This is kept for immediate updates after a trade close, 
        # but sync_daily_stats is the source of truth.
        if profit < 0:
            self.daily_loss += abs(profit)
            self.consecutive_losses += 1
        else:
            self.daily_loss -= profit 
            if self.daily_loss < 0:
                self.daily_loss = 0
            self.consecutive_losses = 0
