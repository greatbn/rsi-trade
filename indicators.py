import pandas as pd
import numpy as np

def rsi(series: pd.Series, period: int = 14) -> pd.Series:
    """
    Calculate RSI using EMA smoothing (Wilder's RSI).
    """
    delta = series.diff()
    up = delta.clip(lower=0)
    down = -1 * delta.clip(upper=0)
    
    # Use exponential moving average for smoothing
    ma_up = up.ewm(alpha=1/period, min_periods=period, adjust=False).mean()
    ma_down = down.ewm(alpha=1/period, min_periods=period, adjust=False).mean()
    
    # Avoid division by zero
    rs = ma_up / ma_down.replace(0, 1e-9)
    rsi_series = 100 - (100 / (1 + rs))
    return rsi_series

def wma(series: pd.Series, period: int) -> pd.Series:
    """
    Calculate Weighted Moving Average.
    """
    weights = np.arange(1, period + 1)
    
    def calc(x):
        return np.dot(x, weights) / weights.sum()
        
    return series.rolling(period).apply(calc, raw=True)

def ema(series: pd.Series, period: int) -> pd.Series:
    """
    Calculate Exponential Moving Average.
    """
    return series.ewm(span=period, adjust=False).mean()
