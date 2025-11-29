import time
import yaml
import logging
from mt5_client import MT5Client
from indicators import rsi, wma, ema
from signal_engine import SignalEngine
from risk_manager import RiskManager
from executor import Executor
from monitor import Monitor

def load_config(path="config.yaml"):
    with open(path, "r") as f:
        return yaml.safe_load(f)

def main():
    # Load Config
    config = load_config()
    
    # Initialize Modules
    mt5 = MT5Client(config['account'])
    monitor = Monitor(config['monitor'], mt5)
    
    if not mt5.initialize():
        monitor.send_alert("Bot failed to start: MT5 connection error.")
        return

    risk_manager = RiskManager(config['risk'], mt5)
    executor = Executor(config['execution'], mt5)
    signal_engine = SignalEngine(config['strategy'])
    
    symbol = config['account']['symbol']
    tf3 = config['strategy']['tf3']
    tf2 = config['strategy']['tf2']
    tf1 = config['strategy']['tf1']
    
    logger = logging.getLogger(__name__)
    logger.info(f"Bot started for {symbol}. TFs: {tf3}, {tf2}, {tf1}")
    
    initial_account_info = mt5.get_account_info()
    initial_balance = initial_account_info.get('balance', 'Unknown')
    logger.info(f"Initial Account Balance: {initial_balance}")
    
    monitor.send_alert(f"Bot started for {symbol}. Balance: {initial_balance}")

    from datetime import datetime, timedelta

    # Initial Risk Sync
    risk_manager.sync_daily_stats()
    
    last_tf1_close_time = None
    last_summary_time = datetime.now()
    last_risk_sync_time = datetime.now()
    last_heartbeat_time = datetime.now()

    try:
        while True:
            # Check for 4-hour Summary
            if datetime.now() - last_summary_time > timedelta(hours=4):
                monitor.send_summary(hours=4)
                last_summary_time = datetime.now()
                
            # Check for 1-hour Heartbeat
            if datetime.now() - last_heartbeat_time > timedelta(hours=1):
                account_info = mt5.get_account_info()
                balance = account_info.get('balance', 0.0)
                monitor.send_heartbeat(balance)
                last_heartbeat_time = datetime.now()
                
            # Periodic Risk Sync (e.g., every 10 minutes)
            if datetime.now() - last_risk_sync_time > timedelta(minutes=10):
                risk_manager.sync_daily_stats()
                last_risk_sync_time = datetime.now()

            # Check Circuit Breaker
            account_info = mt5.get_account_info()
            if not account_info:
                logger.warning("Failed to get account info. Retrying...")
                time.sleep(5)
                continue
                
            if not risk_manager.check_safety(account_info.get('balance', 0)):
                logger.warning("Risk safety check failed. Stopping trading.")
                monitor.send_alert("Risk safety check failed. Bot stopped.")
                break

            # 1. Fetch Candles
            # Fetch enough candles for WMA45 (need at least 45+buffer)
            n_candles = 200 
            df3 = mt5.get_candles(symbol, tf3, n_candles)
            df2 = mt5.get_candles(symbol, tf2, n_candles)
            df1 = mt5.get_candles(symbol, tf1, n_candles)

            if df3.empty or df2.empty or df1.empty:
                logger.warning("Failed to fetch data. Retrying...")
                time.sleep(5)
                continue

            # 2. Compute Indicators
            df3 = signal_engine.compute_indicators(df3)
            df2 = signal_engine.compute_indicators(df2)
            df1 = signal_engine.compute_indicators(df1)

            # 3. Check for New Candle (TF1)
            # We only trade on closed candles of TF1
            current_tf1_close_time = df1.iloc[-1]['time'] # Assuming get_candles returns latest open/closed? 
            # Usually get_candles(..., n) returns latest n candles. The last one might be open.
            # If we want closed candles, we should look at iloc[-2] as the last CLOSED candle.
            # Or we check if a NEW candle has appeared.
            # Let's track the time of the *last processed closed candle*.
            # If df1.iloc[-2]['time'] > last_processed_time, then we have a new closed candle.
            
            # Let's use iloc[-2] as the "Signal Candle".
            signal_candle_time = df1.iloc[-2]['time']
            
            if last_tf1_close_time is None:
                last_tf1_close_time = signal_candle_time
                # First run, maybe don't trade immediately or just set baseline
                logger.info(f"Initialized. Last closed candle time: {last_tf1_close_time}")
            
            elif signal_candle_time > last_tf1_close_time:
                # New candle closed!
                logger.info(f"New candle closed at {signal_candle_time}. Analyzing...")
                
                # Check for existing positions
                open_positions = mt5.get_open_positions(symbol=symbol)
                if open_positions:
                    logger.info(f"Position already open for {symbol}. Skipping new signal generation.")
                    last_tf1_close_time = signal_candle_time
                    continue

                # --- FILTERS ---
                # 1. Time Filter
                current_hour = datetime.now().hour
                start_hour = config.get('filters', {}).get('start_hour', 0)
                end_hour = config.get('filters', {}).get('end_hour', 24)
                
                if not (start_hour <= current_hour < end_hour):
                    logger.info(f"Outside trading hours ({current_hour}:00). Allowed: {start_hour}-{end_hour}. Skipping.")
                    last_tf1_close_time = signal_candle_time
                    continue

                # 2. Spread Filter
                tick = mt5.get_tick(symbol)
                if tick:
                    spread = tick['ask'] - tick['bid']
                    # Convert to points
                    symbol_info = mt5.get_symbol_info(symbol)
                    point = symbol_info.point if symbol_info else 0.00001
                    spread_points = spread / point
                    
                    max_spread = config.get('filters', {}).get('max_spread', 1000)
                    if spread_points > max_spread:
                        logger.warning(f"Spread too high ({spread_points:.1f} > {max_spread}). Skipping.")
                        last_tf1_close_time = signal_candle_time
                        continue
                else:
                    logger.warning("Could not get tick for spread check. Skipping.")
                    continue
                # ---------------
                
                # Generate Signal
                # Note: signal_engine.generate uses iloc[-1] for "current". 
                # If we want to analyze the closed candle, we should pass sliced DFs or adjust logic.
                # Adjusting logic: signal_engine uses iloc[-1] as "current". 
                # If we pass df1 (where -1 is open, -2 is closed), and we want to trade based on -2 closing...
                # Actually, standard practice: 
                # -1 is forming candle. -2 is last closed candle.
                # Signal engine checks crossover between -2 and -1? No, usually between -3 and -2 (completed crossover).
                # OR check crossover happening NOW in forming candle? (Repainting risk).
                # User spec: "TF1 xác nhận entry (EMA9 x WMA45...)"
                # "Signal object ... tf1_close_time"
                # "Wait for nến TF1 đóng"
                # So we should evaluate the candle that JUST closed (index -2).
                # To make signal_engine logic work (which uses -1 and -2), we can pass `df.iloc[:-1]` (exclude forming candle).
                # Then -1 becomes the closed candle, -2 becomes the one before it.
                
                df3_closed = df3.iloc[:-1]
                df2_closed = df2.iloc[:-1]
                df1_closed = df1.iloc[:-1]
                
                # Get symbol point for Fixed SL calculation
                symbol_info = mt5.get_symbol_info(symbol)
                point = symbol_info.point if symbol_info else None
                
                signal = signal_engine.generate(df3_closed, df2_closed, df1_closed, symbol, point=point)
                
                if signal:
                    logger.info(f"Signal Generated: {signal}")
                    
                    # Risk Sizing
                    balance = account_info.get('balance', 0)
                    lot_size = risk_manager.compute_lot_size(symbol, signal.sl_price, signal.entry_price, balance)
                    
                    if lot_size > 0:
                        # Execute
                        result = executor.execute_signal(signal, lot_size)
                        if result:
                            monitor.send_trade_notification(signal, lot_size, result)
                            # Update metrics? (Only on close, but we can track open)
                    else:
                        logger.warning("Lot size 0. Skipping trade.")
                
                last_tf1_close_time = signal_candle_time

            # Sleep
            time.sleep(config['monitor']['poll_interval'])

    except KeyboardInterrupt:
        logger.info("Stopping bot...")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        monitor.send_alert(f"Bot crashed: {e}")
    finally:
        mt5.shutdown()

if __name__ == "__main__":
    main()
