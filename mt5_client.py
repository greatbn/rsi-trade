import MetaTrader5 as mt5
import pandas as pd
import time
import logging

logger = logging.getLogger(__name__)

class MT5Client:
    def __init__(self, config):
        self.config = config
        self.connected = False

    def initialize(self) -> bool:
        """
        Initialize connection to MT5 with retry logic.
        """
        max_retries = 3
        for attempt in range(max_retries):
            try:
                # Attempt to initialize with specific account if provided, else default
                if self.config.get('login') and self.config.get('password'):
                    authorized = mt5.initialize(
                        login=self.config['login'],
                        password=self.config['password'],
                        server=self.config['server']
                    )
                else:
                    authorized = mt5.initialize()

                if authorized:
                    self.connected = True
                    logger.info(f"Connected to MT5: {mt5.terminal_info()}")
                    return True
                else:
                    error_code = mt5.last_error()
                    logger.warning(f"MT5 initialize failed (Attempt {attempt+1}/{max_retries}), error: {error_code}")
                    time.sleep(1)
            except Exception as e:
                logger.error(f"Exception during MT5 initialize: {e}")
                time.sleep(1)
        
        logger.critical("Failed to connect to MT5 after retries.")
        return False

    def shutdown(self):
        mt5.shutdown()
        self.connected = False
        logger.info("MT5 connection shutdown.")

    def check_connection(self) -> bool:
        """
        Check if connected to MT5, attempt to reconnect if not.
        """
        if not mt5.terminal_info():
            logger.warning("MT5 connection lost. Attempting to reconnect...")
            self.connected = False
            return self.initialize()
        return True

    def get_candles(self, symbol: str, timeframe_str: str, n: int) -> pd.DataFrame:
        """
        Fetch n candles for symbol and timeframe.
        timeframe_str: "M1", "M5", "M15", "M30", "H1", "H4", "D1", "W1", "MN1"
        """
        tf_map = {
            "M1": mt5.TIMEFRAME_M1,
            "M5": mt5.TIMEFRAME_M5,
            "M15": mt5.TIMEFRAME_M15,
            "M30": mt5.TIMEFRAME_M30,
            "H1": mt5.TIMEFRAME_H1,
            "H4": mt5.TIMEFRAME_H4,
            "D1": mt5.TIMEFRAME_D1,
            "W1": mt5.TIMEFRAME_W1,
            "MN1": mt5.TIMEFRAME_MN1
        }
        
        mt5_tf = tf_map.get(timeframe_str)
        if mt5_tf is None:
            logger.error(f"Invalid timeframe: {timeframe_str}")
            return pd.DataFrame()

        rates = mt5.copy_rates_from_pos(symbol, mt5_tf, 0, n)
        
        if rates is None:
            logger.error(f"Failed to get rates for {symbol} {timeframe_str}")
            return pd.DataFrame()
            
        df = pd.DataFrame(rates)
        df['time'] = pd.to_datetime(df['time'], unit='s')
        return df

    def get_tick(self, symbol: str) -> dict:
        tick = mt5.symbol_info_tick(symbol)
        if tick is None:
            logger.error(f"Failed to get tick for {symbol}")
            return {}
        return {'ask': tick.ask, 'bid': tick.bid, 'last': tick.last}

    def get_symbol_info(self, symbol: str):
        return mt5.symbol_info(symbol)

    def place_order_market(self, symbol: str, volume: float, side: str, sl: float=None, tp: float=None, deviation:int=20, comment:str=None, magic:int=0) -> dict:
        """
        Place a market order.
        side: 'BUY' or 'SELL'
        """
        tick = self.get_tick(symbol)
        if not tick:
            return {'retcode': -1, 'comment': "No tick data"}

        action_type = mt5.ORDER_TYPE_BUY if side == 'BUY' else mt5.ORDER_TYPE_SELL
        price = tick['ask'] if side == 'BUY' else tick['bid']
        
        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": volume,
            "type": action_type,
            "price": price,
            "deviation": deviation,
            "magic": magic,
            "comment": comment if comment else "",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }
        
        if sl:
            request["sl"] = sl
        if tp:
            request["tp"] = tp
            
        result = mt5.order_send(request)
        
        if result is None:
             return {'retcode': -1, 'comment': "Order send failed (None result)"}
             
        return result._asdict()

    def modify_position(self, ticket: int, sl: float = None, tp: float = None) -> bool:
        """
        Modify SL/TP of an existing position.
        """
        # Get position details first to verify it exists
        positions = mt5.positions_get(ticket=ticket)
        if not positions:
            logger.error(f"Position {ticket} not found for modification.")
            return False
            
        position = positions[0]
        
        request = {
            "action": mt5.TRADE_ACTION_SLTP,
            "position": ticket,
            "symbol": position.symbol,
            "sl": sl if sl is not None else position.sl,
            "tp": tp if tp is not None else position.tp,
        }
        
        result = mt5.order_send(request)
        if result is None:
            logger.error(f"Failed to modify position {ticket} (None result)")
            return False
            
        if result.retcode != mt5.TRADE_RETCODE_DONE:
            logger.error(f"Failed to modify position {ticket}, retcode: {result.retcode}")
            return False
            
        logger.info(f"Position {ticket} modified. New SL: {sl}, New TP: {tp}")
        return True

    def get_account_info(self) -> dict:
        info = mt5.account_info()
        if info is None:
            return {}
        return info._asdict()

    def get_open_positions(self, symbol: str=None) -> list:
        if symbol:
            positions = mt5.positions_get(symbol=symbol)
        else:
            positions = mt5.positions_get()
            
        if positions is None:
            return []
            
        return [p._asdict() for p in positions]

    def get_history_deals(self, from_date, to_date) -> list:
        """
        Fetch history deals within the specified time range.
        """
        deals = mt5.history_deals_get(from_date, to_date)
        if deals is None:
            return []
        return [d._asdict() for d in deals]
