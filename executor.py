import logging
import time

logger = logging.getLogger(__name__)

class Executor:
    def __init__(self, config, mt5_client):
        self.config = config
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
                deviation=self.config['deviation'],
                comment=f"RSI Bot {signal.reason}",
                magic=self.config['magic']
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
