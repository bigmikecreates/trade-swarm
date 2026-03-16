"""OHLCV data fetcher using Yahoo Finance."""

import yfinance as yf
import pandas as pd


def fetch_ohlcv(symbol: str, period: str = "2y", interval: str = "1h") -> pd.DataFrame:
    df = yf.download(symbol, period=period, interval=interval, progress=False)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df.dropna(inplace=True)
    return df
