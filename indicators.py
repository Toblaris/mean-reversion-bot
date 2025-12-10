import numpy as np
import pandas as pd

def rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    up = delta.clip(lower=0)
    down = -1 * delta.clip(upper=0)
    ma_up = up.ewm(alpha=1/period, min_periods=period).mean()
    ma_down = down.ewm(alpha=1/period, min_periods=period).mean()
    rs = ma_up / ma_down
    return 100 - (100 / (1 + rs))

def bollinger_bands(series: pd.Series, period: int = 20, std_multiplier: float = 2.0):
    sma = series.rolling(period).mean()
    std = series.rolling(period).std()
    upper = sma + (std_multiplier * std)
    lower = sma - (std_multiplier * std)
    return sma, upper, lower

def percent_change(series: pd.Series, lookback: int) -> float:
    if len(series) < lookback + 1:
        return 0.0
    return (series.iloc[-1] - series.iloc[-1 - lookback]) / series.iloc[-1 - lookback] * 100.0