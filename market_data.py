from __future__ import annotations

import math

import pandas as pd
import yfinance as yf

from models import MarketSnapshot


MACRO_TICKERS = {
    "SPY": "SPY",
    "QQQ": "QQQ",
    "IWM": "IWM",
    "VIX": "^VIX",
    "US10Y": "^TNX",
    "DXY": "DX-Y.NYB",
    "OIL": "CL=F",
}


def _finite(value):
    if value is None:
        return None
    try:
        value = float(value)
        return value if math.isfinite(value) else None
    except (TypeError, ValueError):
        return None


def get_snapshot(ticker: str) -> MarketSnapshot:
    try:
        hist = yf.download(
            ticker,
            period="6mo",
            interval="1d",
            auto_adjust=True,
            progress=False,
            threads=False,
        )
    except Exception:
        hist = pd.DataFrame()

    if hist.empty:
        return MarketSnapshot(ticker=ticker)

    if isinstance(hist.columns, pd.MultiIndex):
        hist.columns = hist.columns.get_level_values(0)
    hist = hist.dropna(subset=["Close"])
    close = hist["Close"]
    volume = hist["Volume"] if "Volume" in hist else pd.Series(index=hist.index, dtype=float)

    def pct(periods: int):
        if len(close) <= periods:
            return None
        return _finite((close.iloc[-1] / close.iloc[-1 - periods] - 1) * 100)

    avg_volume = volume.tail(20).mean() if len(volume) else None
    relative_volume = (
        _finite(volume.iloc[-1] / avg_volume)
        if avg_volume is not None and avg_volume > 0 and len(volume)
        else None
    )
    ma20 = close.tail(20).mean() if len(close) >= 20 else None
    ma50 = close.tail(50).mean() if len(close) >= 50 else None

    return MarketSnapshot(
        ticker=ticker,
        price=_finite(close.iloc[-1]),
        change_1d_pct=pct(1),
        change_5d_pct=pct(5),
        change_20d_pct=pct(20),
        relative_volume_20d=relative_volume,
        above_20d_ma=bool(close.iloc[-1] > ma20) if ma20 is not None else None,
        above_50d_ma=bool(close.iloc[-1] > ma50) if ma50 is not None else None,
    )


def get_macro_context() -> dict[str, MarketSnapshot]:
    return {name: get_snapshot(symbol) for name, symbol in MACRO_TICKERS.items()}
