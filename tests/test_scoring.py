from datetime import UTC, datetime

from models import NewsItem
from scoring import rule_based_analysis, source_quality


def test_sec_source_quality():
    assert source_quality("SEC EDGAR", "https://www.sec.gov/test") >= 95


def test_positive_contract():
    news = NewsItem(
        ticker="RKLB",
        headline="Rocket Lab wins major government contract",
        summary="The company was awarded a multi-year contract.",
        source="Reuters",
        url="https://reuters.com/example",
        published_at=datetime.now(UTC),
        provider="finnhub",
    )
    result = rule_based_analysis(news, {"RKLB": {"sector_peers": ["SPCX"]}})
    assert result.company_impact > 0
    assert "SPCX" in result.affected_tickers


def test_dilution_negative():
    news = NewsItem(
        ticker="XYZ",
        headline="Company announces secondary offering and dilution",
        source="Company IR",
        published_at=datetime.now(UTC),
        provider="yfinance",
    )
    result = rule_based_analysis(news, {})
    assert result.company_impact < 0
