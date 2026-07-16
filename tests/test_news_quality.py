from datetime import UTC, datetime

from models import MarketSnapshot, NewsItem
from news_sources import attribute_news_item, dedupe_news
from scoring import macro_regime_score


def item(ticker: str, headline: str, url: str = "") -> NewsItem:
    return NewsItem(
        ticker=ticker,
        requested_ticker=ticker,
        headline=headline,
        source="Example",
        url=url,
        published_at=datetime.now(UTC),
        provider="yfinance",
    )


def test_marvell_article_from_spy_is_reassigned():
    news = attribute_news_item(
        item("SPY", "Marvell Crashed Below $200: This Wall Street Firm Thinks It Doubles From Here")
    )
    assert news.ticker == "MRVL"
    assert news.requested_ticker == "SPY"
    assert news.relevance_score >= 90


def test_apple_article_is_not_assigned_to_google():
    news = attribute_news_item(
        item("GOOGL", "Why Apple's Standard Oil Strategy Is Driving the Stock to All-Time Highs")
    )
    assert news.ticker == "AAPL"
    assert news.relevance_score >= 90


def test_generic_decliners_article_is_penalized():
    news = attribute_news_item(item("ASTS", "Top Midday Decliners"))
    assert news.is_broad_article is True
    assert news.relevance_score < 60


def test_duplicate_urls_keep_one():
    a = attribute_news_item(item("AAPL", "Apple Announces New Product", "https://example.com/x?utm_source=a"))
    b = attribute_news_item(item("GOOGL", "Apple Announces New Product", "https://example.com/x?utm_source=b"))
    assert len(dedupe_news([a, b])) == 1


def test_macro_regime_detects_risk_off():
    macro = {
        "SPY": MarketSnapshot(ticker="SPY", change_1d_pct=-0.54),
        "QQQ": MarketSnapshot(ticker="QQQ", change_1d_pct=-1.64),
        "IWM": MarketSnapshot(ticker="IWM", change_1d_pct=-0.06),
        "VIX": MarketSnapshot(ticker="^VIX", change_1d_pct=6.76),
        "US10Y": MarketSnapshot(ticker="^TNX", change_1d_pct=0.53),
        "DXY": MarketSnapshot(ticker="DXY", change_1d_pct=0.23),
    }
    score, confidence, evidence = macro_regime_score(macro)
    assert score <= -30
    assert confidence == 100
    assert len(evidence) == 6
