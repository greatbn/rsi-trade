import unittest
import pandas as pd
import numpy as np
from signal_engine import SignalEngine, Signal

class TestSignalEngine(unittest.TestCase):
    def setUp(self):
        self.config = {
            'rsi_period': 14,
            'wma_period': 45,
            'ema_period': 9,
            'bias_rsi_threshold_high': 75,
            'bias_rsi_threshold_low': 25,
            'rsi_upper': 75,
            'rsi_lower': 25,
            'tf2_zone_tolerance': 5,
            'sl_method': 'swing',
            'swing_lookback': 5,
            'tp_rr': 1.5
        }
        self.engine = SignalEngine(self.config)

    def create_mock_df(self, rsi_val, wma_val, ema_val, close_val=100):
        # Create a DF with enough rows, setting the last row to desired values
        df = pd.DataFrame({
            'close': [close_val] * 50,
            'time': pd.date_range(start='2023-01-01', periods=50, freq='H')
        })
        # Mock indicators directly to avoid calculation logic in test
        df['rsi'] = rsi_val
        df['rsi_wma'] = wma_val
        df['rsi_ema'] = ema_val
        
        # For swing low/high
        df['low'] = close_val - 1
        df['high'] = close_val + 1
        
        return df

    def test_generate_long_signal(self):
        # TF3: Bias LONG (RSI > 75)
        df3 = self.create_mock_df(rsi_val=80, wma_val=50, ema_val=50)
        
        # TF2: In Zone (RSI near WMA)
        df2 = self.create_mock_df(rsi_val=50, wma_val=50, ema_val=50)
        
        # TF1: Confirmation (Crossover: Prev EMA < WMA, Curr EMA > WMA)
        df1 = self.create_mock_df(rsi_val=50, wma_val=50, ema_val=51)
        # Manually set prev row for crossover
        df1.iloc[-2, df1.columns.get_loc('rsi_ema')] = 49
        df1.iloc[-2, df1.columns.get_loc('rsi_wma')] = 50
        
        signal = self.engine.generate(df3, df2, df1, "TEST")
        
        self.assertIsNotNone(signal)
        self.assertEqual(signal.side, 'LONG')
        self.assertEqual(signal.symbol, 'TEST')

    def test_no_signal_bias_short(self):
        # TF3: Bias SHORT (RSI < 25)
        df3 = self.create_mock_df(rsi_val=20, wma_val=50, ema_val=50)
        
        # TF2: In Zone
        df2 = self.create_mock_df(rsi_val=50, wma_val=50, ema_val=50)
        
        # TF1: Long Crossover (Should be ignored because Bias is SHORT)
        df1 = self.create_mock_df(rsi_val=50, wma_val=50, ema_val=51)
        df1.iloc[-2, df1.columns.get_loc('rsi_ema')] = 49
        df1.iloc[-2, df1.columns.get_loc('rsi_wma')] = 50
        
        signal = self.engine.generate(df3, df2, df1, "TEST")
        self.assertIsNone(signal)

if __name__ == '__main__':
    unittest.main()
