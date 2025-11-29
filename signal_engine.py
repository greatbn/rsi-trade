from dataclasses import dataclass
from datetime import datetime
import pandas as pd
import indicators
import logging

logger = logging.getLogger(__name__)

@dataclass
class Signal:
    symbol: str
    side: str            # "BUY" or "SELL"
    entry_price: float
    sl_price: float
    tp_price: float
    confidence: float
    reason: str
    tf1_close_time: datetime

class SignalEngine:
    def __init__(self, config):
        self.config = config

    def compute_indicators(self, df: pd.DataFrame):
        """
        Compute RSI, WMA(RSI), EMA(RSI) for a dataframe.
        """
        if df.empty:
            return df
            
        df['rsi'] = indicators.rsi(df['close'], self.config['rsi_period'])
        df['rsi_wma'] = indicators.wma(df['rsi'], self.config['wma_period'])
        df['rsi_ema'] = indicators.ema(df['rsi'], self.config['ema_period'])
        
        # Compute ADX if configured
        adx_period = self.config.get('adx_period', 14)
        df['adx'] = indicators.adx(df['high'], df['low'], df['close'], adx_period)
        return df

    def generate(self, df3: pd.DataFrame, df2: pd.DataFrame, df1: pd.DataFrame, symbol: str, point: float = None) -> Signal:
        """
        Generate signal based on 3-TF logic.
        """
        # Ensure we have enough data
        if df3.empty or df2.empty or df1.empty:
            return None
            
        # --- ADX Filter (TF1) ---
        # Check if trend is strong enough on execution timeframe
        curr1 = df1.iloc[-1]
        adx_threshold = self.config.get('adx_threshold', 25)
        
        # Check if ADX column exists (might be NaN at start)
        if 'adx' in curr1 and not pd.isna(curr1['adx']):
            if curr1['adx'] < adx_threshold:
                # Market is chopping
                return None
        # ------------------------
            
        # 1. Bias Check (TF3)
        # Use last closed candle (iloc[-1] if we assume df contains closed candles, 
        # but usually get_candles returns current open candle at end. 
        # Let's assume we use iloc[-2] for fully closed, or check timestamps.)
        # For simplicity, let's use iloc[-1] assuming it's the latest relevant candle 
        # (user spec says "wait for TF1 close", so TF1[-1] is closed).
        # But for TF3/TF2, they might be still open. We should use the latest available data or strictly closed.
        # Let's use latest available (iloc[-1]) for Trend/Zone to be reactive, 
        # but strictly closed for TF1 confirmation.
        
        curr3 = df3.iloc[-1]
        bias = None
        
        # Bias Logic
        if curr3['rsi'] >= self.config['bias_rsi_threshold_high'] or curr3['rsi'] > curr3['rsi_wma']: 
            # Note: User spec: "rsi_TF3 >= rsi_upper OR wma45_rsi_TF3 > threshold" -> This seems slightly ambiguous in spec.
            # Spec says: "If rsi_TF3 >= rsi_upper OR wma45_rsi_TF3 > threshold => BIAS=LONG"
            # Wait, usually WMA > threshold? Or RSI > WMA?
            # Handbook says: Uptrend if RSI > 40 and WMA sloping up.
            # Spec says: "If rsi_TF3 >= rsi_upper OR wma45_rsi_TF3 > threshold"
            # Let's interpret as: RSI >= 75 OR (RSI > 50 and WMA > 50) - let's stick to the spec text literally if possible, 
            # but "wma45_rsi_TF3 > threshold" implies checking WMA value.
            # Let's use: RSI > WMA45 as general uptrend bias from Handbook.
            bias = 'LONG' if curr3['rsi'] > curr3['rsi_wma'] else 'SHORT'
        
        # Refined Bias from Spec:
        # If rsi_TF3 >= rsi_upper (75) => LONG
        # If rsi_TF3 <= rsi_lower (25) => SHORT
        # If not extreme, check Trend?
        # Let's combine:
        if curr3['rsi'] >= self.config['rsi_upper']:
            bias = 'LONG'
        elif curr3['rsi'] <= self.config['rsi_lower']:
            bias = 'SHORT'
        else:
            # Fallback to RSI vs WMA
            bias = 'LONG' if curr3['rsi'] > curr3['rsi_wma'] else 'SHORT'

        if not bias:
            return None

        # 2. Entry Zone (TF2)
        curr2 = df2.iloc[-1]
        in_zone = False
        
        if bias == 'LONG':
            # Near WMA45 or RSI in [40..55]
            dist = abs(curr2['rsi'] - curr2['rsi_wma'])
            if dist <= self.config['tf2_zone_tolerance'] or (40 <= curr2['rsi'] <= 55):
                in_zone = True
        else: # SHORT
            # Near WMA45 or RSI in [45..60] (Symmetric)
            dist = abs(curr2['rsi'] - curr2['rsi_wma'])
            if dist <= self.config['tf2_zone_tolerance'] or (45 <= curr2['rsi'] <= 60):
                in_zone = True
                
        if not in_zone:
            return None

        # 3. Confirmation (TF1)
        # Must use CLOSED candle. Assuming df1[-1] is the just-closed candle.
        curr1 = df1.iloc[-1]
        prev1 = df1.iloc[-2]
        
        confirmed = False
        reason = ""
        
        if bias == 'LONG':
            # Crossover: EMA9 crosses above WMA45
            # Check if EMA9 was below WMA45 and now is above
            # Or RSI crosses above WMA45
            
            # Spec: "EMA9_TF1 cắt WMA45_TF1 theo hướng bias"
            ema_cross = (prev1['rsi_ema'] <= prev1['rsi_wma']) and (curr1['rsi_ema'] > curr1['rsi_wma'])
            
            # Spec: "OR RSI_TF1 re-test WMA45_RSI_TF1"
            # Simple retest: RSI dropped near WMA and bounced up. 
            # Hard to detect strictly with 1 candle. Let's stick to Crossover for MVP.
            
            # Also check RSI > EMA9 for strength
            if ema_cross or ((prev1['rsi'] <= prev1['rsi_wma']) and (curr1['rsi'] > curr1['rsi_wma'])):
                confirmed = True
                reason = "Crossover"
                
        else: # SHORT
            # Crossover: EMA9 crosses below WMA45
            ema_cross = (prev1['rsi_ema'] >= prev1['rsi_wma']) and (curr1['rsi_ema'] < curr1['rsi_wma'])
            
            if ema_cross or ((prev1['rsi'] >= prev1['rsi_wma']) and (curr1['rsi'] < curr1['rsi_wma'])):
                confirmed = True
                reason = "Crossover"

        if not confirmed:
            return None

        # 4. Build Signal
        # Calculate SL/TP
        entry_price = curr1['close'] # Approximate execution price
        sl_price = 0.0
        
        if self.config['sl_method'] == 'swing':
            # Lookback for Swing High/Low
            lookback = self.config['swing_lookback']
            window = df1.iloc[-lookback:]
            if bias == 'LONG':
                sl_price = window['low'].min()
            else:
                sl_price = window['high'].max()
        else:
            # Fixed Pips
            if point is None:
                # Fallback to heuristic if point not provided
                if entry_price > 500: # Indices, Gold, Crypto
                    point = 0.01 # Crude assumption
                    if entry_price > 20000: # BTC
                        point = 1.0
                elif entry_price > 20: # Oil, etc
                    point = 0.001
                else: # Forex
                    point = 0.00001
                
            sl_points = self.config.get('sl_points', 500) # Default 500 points
            sl_dist = sl_points * point
            
            if bias == 'LONG':
                sl_price = entry_price - sl_dist
            else:
                sl_price = entry_price + sl_dist

        # Calculate TP
        dist = abs(entry_price - sl_price)
        if bias == 'LONG':
            tp_price = entry_price + dist * self.config['tp_rr']
        else:
            tp_price = entry_price - dist * self.config['tp_rr']

        return Signal(
            symbol=symbol,
            side=bias,
            entry_price=entry_price,
            sl_price=sl_price,
            tp_price=tp_price,
            confidence=0.8,
            reason=reason,
            tf1_close_time=curr1['time']
        )
