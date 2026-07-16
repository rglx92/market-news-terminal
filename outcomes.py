from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pandas as pd
import yfinance as yf

from storage import pending_outcomes, upsert_outcome


def _return(base: float, target: float) -> float:
    return round((target / base - 1.0) * 100.0, 4)


def calculate_outcome(ticker: str, published_at: str):
    published = datetime.fromisoformat(published_at.replace("Z", "+00:00"))
    if published.tzinfo is None:
        published = published.replace(tzinfo=UTC)
    start = (published.date() - timedelta(days=7)).isoformat()
    end = (published.date() + timedelta(days=14)).isoformat()
    try:
        hist = yf.download(
            ticker,
            start=start,
            end=end,
            interval="1d",
            auto_adjust=True,
            progress=False,
            threads=False,
            timeout=8,
        )
    except Exception:
        return None
    if hist.empty:
        return None
    if isinstance(hist.columns, pd.MultiIndex):
        hist.columns = hist.columns.get_level_values(0)
    hist = hist.dropna(subset=["Close"])
    session_dates = [idx.date() for idx in hist.index]

    # Aproximación reproducible: cierre anterior a la fecha de publicación como base.
    prior_positions = [i for i, d in enumerate(session_dates) if d < published.date()]
    if not prior_positions:
        return None
    base_pos = prior_positions[-1]
    base = float(hist["Close"].iloc[base_pos])

    values = []
    for sessions in (1, 3, 5):
        target_pos = base_pos + sessions
        if target_pos >= len(hist):
            values.append(None)
        else:
            values.append(_return(base, float(hist["Close"].iloc[target_pos])))
    return tuple(values)


def update_pending_outcomes(limit: int = 100) -> dict[str, int]:
    updated = 0
    skipped = 0
    for analysis_id, ticker, published_at, _impact in pending_outcomes(limit):
        result = calculate_outcome(ticker, published_at)
        if result is None or all(v is None for v in result):
            skipped += 1
            continue
        upsert_outcome(analysis_id, *result)
        updated += 1
    return {"updated": updated, "skipped": skipped}
