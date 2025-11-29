import unittest
import pandas as pd
import numpy as np
from indicators import rsi, wma, ema

class TestIndicators(unittest.TestCase):
    def setUp(self):
        self.data = pd.Series(np.random.randn(100) + 100) # Random price data

    def test_ema(self):
        result = ema(self.data, 9)
        self.assertEqual(len(result), 100)
        self.assertFalse(result.isnull().all())

    def test_wma(self):
        result = wma(self.data, 45)
        self.assertEqual(len(result), 100)
        # First 44 should be NaN
        self.assertTrue(result.iloc[43].astype(str) == 'nan' or np.isnan(result.iloc[43]))
        self.assertFalse(np.isnan(result.iloc[44]))

    def test_rsi(self):
        result = rsi(self.data, 14)
        self.assertEqual(len(result), 100)
        # Drop NaNs before checking range
        valid_result = result.dropna()
        self.assertTrue((valid_result >= 0).all() and (valid_result <= 100).all())

if __name__ == '__main__':
    unittest.main()
