from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv

from analyzer import analyze_news
from market_data import get_macro_context, get_snapshot
from models import ScoredAnalysis
from news_sources import fetch_news_for_watchlist
from scoring import aggregate_spy_bias, trade_quality_score
from storage import save_analysis


BASE_DIR = Path(__file__).parent
load_dotenv(BASE_DIR / ".env")
RELATIONSHIPS = json.loads((BASE_DIR / "relationships.json").read_text(encoding="utf-8"))


def load_watchlist() -> list[str]:
    path = BASE_DIR / "watchlist.txt"
    return [
        line.strip().upper()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.startswith("#")
    ]


def main() -> None:
    tickers = load_watchlist()
    days = int(os.getenv("DAILY_LOOKBACK_DAYS", "2"))
    max_news = int(os.getenv("DAILY_MAX_NEWS_PER_TICKER", "4"))
    minimum_trade = int(os.getenv("DAILY_MIN_TRADE_QUALITY", "35"))
    minimum_relevance = int(os.getenv("DAILY_MIN_RELEVANCE", "60"))

    macro = get_macro_context()
    spy_snapshot = macro.get("SPY") or get_snapshot("SPY")
    news_items = fetch_news_for_watchlist(
        tickers,
        days=days,
        max_per_ticker=max_news,
        minimum_relevance=minimum_relevance,
    )
    rows: list[dict] = []
    scored_items: list[ScoredAnalysis] = []
    snapshots = {"SPY": spy_snapshot}

    for news in news_items:
        print(f"Analizando {news.ticker}: {news.headline[:70]}")
        if news.ticker not in snapshots:
            snapshots[news.ticker] = get_snapshot(news.ticker)
        company_snapshot = snapshots[news.ticker]
        analysis, mode, ai_error = analyze_news(
            news, company_snapshot, spy_snapshot, macro, RELATIONSHIPS
        )
        trade_quality, confirmation = trade_quality_score(
            analysis,
            company_snapshot,
            spy_snapshot,
            relevance_score=news.relevance_score,
        )
        scored = ScoredAnalysis(
            news=news,
            analysis=analysis,
            trade_quality=trade_quality,
            market_confirmation=confirmation,
            company_snapshot=company_snapshot,
            spy_snapshot=spy_snapshot,
            mode=mode,
            ai_error=ai_error,
        )
        save_analysis(scored)
        scored_items.append(scored)
        if trade_quality < minimum_trade:
            continue
        rows.append(
            {
                "published_at": news.published_at.isoformat(),
                "ticker": news.ticker,
                "requested_ticker": news.requested_ticker,
                "headline": news.headline,
                "source": news.source,
                "url": news.url,
                "relevance": news.relevance_score,
                "relevance_reason": news.relevance_reason,
                "event_type": analysis.event_type,
                "company_impact": analysis.company_impact,
                "spy_impact": analysis.spy_impact,
                "trade_quality": trade_quality,
                "market_confirmation": confirmation,
                "confidence": analysis.confidence,
                "already_priced_probability": analysis.already_priced_probability,
                "horizon": analysis.horizon,
                "thesis": analysis.thesis,
                "mode": mode,
                "ai_error": ai_error,
            }
        )

    spy_bias, spy_confidence, macro_score, _ = aggregate_spy_bias(scored_items, macro)
    for row in rows:
        row["aggregate_spy_bias"] = round(spy_bias, 2)
        row["aggregate_spy_confidence"] = round(spy_confidence, 2)
        row["macro_regime_score"] = macro_score

    reports_dir = BASE_DIR / "reports"
    reports_dir.mkdir(exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%d_%H%M")
    df = pd.DataFrame(rows)
    if not df.empty:
        df = df.sort_values(["trade_quality", "confidence"], ascending=False)
    csv_path = reports_dir / f"market_news_{stamp}.csv"
    html_path = reports_dir / f"market_news_{stamp}.html"
    df.to_csv(csv_path, index=False)
    df.to_html(html_path, index=False, escape=True)
    print(f"Reporte CSV: {csv_path}")
    print(f"Reporte HTML: {html_path}")


if __name__ == "__main__":
    main()
