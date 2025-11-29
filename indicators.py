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

def adx(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
    """
    Calculate Average Directional Index (ADX).
    """
    # 1. Calculate True Range (TR)
    tr1 = high - low
    tr2 = (high - close.shift(1)).abs()
    tr3 = (low - close.shift(1)).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    
    # 2. Calculate Directional Movement (+DM, -DM)
    up_move = high - high.shift(1)
    down_move = low.shift(1) - low
    
    plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
    minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)
    
    plus_dm = pd.Series(plus_dm, index=high.index)
    minus_dm = pd.Series(minus_dm, index=high.index)
    
    # 3. Smooth TR, +DM, -DM (Wilder's Smoothing: alpha=1/period)
    # Note: Wilder's smoothing is equivalent to EMA with alpha=1/period
    tr_smooth = tr.ewm(alpha=1/period, min_periods=period, adjust=False).mean()
    plus_dm_smooth = plus_dm.ewm(alpha=1/period, min_periods=period, adjust=False).mean()
    minus_dm_smooth = minus_dm.ewm(alpha=1/period, min_periods=period, adjust=False).mean()
    
    # 4. Calculate +DI, -DI
    plus_di = 100 * (plus_dm_smooth / tr_smooth.replace(0, 1e-9))
    minus_di = 100 * (minus_dm_smooth / tr_smooth.replace(0, 1e-9))
    
    # 5. Calculate DX
    dx = 100 * (abs(plus_di - minus_di) / (plus_di + minus_di).replace(0, 1e-9))
    
    # 6. Calculate ADX (Smoothed DX)
    adx_series = dx.ewm(alpha=1/period, min_periods=period, adjust=False).mean()
    
    return adx_series
