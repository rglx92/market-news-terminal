from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta
from urllib.parse import urlparse

import requests
import yfinance as yf

from models import NewsItem


TIMEOUT = 20


def _safe_dt(value) -> datetime:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=UTC)
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value, tz=UTC)
    if isinstance(value, str):
        try:
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
            return dt if dt.tzinfo else dt.replace(tzinfo=UTC)
        except ValueError:
            pass
    return datetime.now(UTC)


def fetch_finnhub_news(ticker: str, days: int = 2) -> list[NewsItem]:
    api_key = os.getenv("FINNHUB_API_KEY", "").strip()
    if not api_key:
        return []
    end = datetime.now(UTC).date()
    start = end - timedelta(days=days)
    response = requests.get(
        "https://finnhub.io/api/v1/company-news",
        params={"symbol": ticker, "from": start.isoformat(), "to": end.isoformat(), "token": api_key},
        timeout=TIMEOUT,
    )
    response.raise_for_status()
    items: list[NewsItem] = []
    for row in response.json():
        headline = (row.get("headline") or "").strip()
        if not headline:
            continue
        items.append(
            NewsItem(
                ticker=ticker,
                headline=headline,
                summary=(row.get("summary") or "").strip(),
                source=(row.get("source") or "Finnhub").strip(),
                url=(row.get("url") or "").strip(),
                published_at=_safe_dt(row.get("datetime")),
                provider="finnhub",
                category=(row.get("category") or "company").strip(),
            )
        )
    return items


def fetch_yfinance_news(ticker: str, days: int = 3) -> list[NewsItem]:
    cutoff = datetime.now(UTC) - timedelta(days=days)
    items: list[NewsItem] = []
    try:
        raw = yf.Ticker(ticker).news or []
    except Exception:
        return []

    for row in raw:
        content = row.get("content", row)
        headline = (content.get("title") or row.get("title") or "").strip()
        if not headline:
            continue
        canonical = content.get("canonicalUrl") or {}
        click_through = content.get("clickThroughUrl") or {}
        url = (
            canonical.get("url")
            or click_through.get("url")
            or content.get("link")
            or row.get("link")
            or ""
        )
        provider_obj = content.get("provider") or {}
        source = provider_obj.get("displayName") or row.get("publisher") or urlparse(url).netloc or "Yahoo Finance"
        published = _safe_dt(content.get("pubDate") or row.get("providerPublishTime"))
        if published < cutoff:
            continue
        summary = content.get("summary") or content.get("description") or ""
        items.append(
            NewsItem(
                ticker=ticker,
                headline=headline,
                summary=str(summary).strip(),
                source=str(source).strip(),
                url=str(url).strip(),
                published_at=published,
                provider="yfinance",
                category="company",
            )
        )
    return items


def _sec_headers() -> dict[str, str]:
    return {
        "User-Agent": os.getenv(
            "SEC_USER_AGENT", "MarketNewsTerminal/0.1 contact@example.com"
        ),
        "Accept-Encoding": "gzip, deflate",
    }


def _ticker_to_cik(ticker: str) -> str | None:
    response = requests.get(
        "https://www.sec.gov/files/company_tickers.json",
        headers=_sec_headers(),
        timeout=TIMEOUT,
    )
    response.raise_for_status()
    target = ticker.upper().replace("-", ".")
    for row in response.json().values():
        if str(row.get("ticker", "")).upper() == target:
            return str(row["cik_str"]).zfill(10)
    return None


def fetch_sec_filings(ticker: str, days: int = 7) -> list[NewsItem]:
    try:
        cik = _ticker_to_cik(ticker)
        if not cik:
            return []
        response = requests.get(
            f"https://data.sec.gov/submissions/CIK{cik}.json",
            headers=_sec_headers(),
            timeout=TIMEOUT,
        )
        response.raise_for_status()
        data = response.json()
    except Exception:
        return []

    recent = data.get("filings", {}).get("recent", {})
    forms = recent.get("form", [])
    dates = recent.get("filingDate", [])
    accessions = recent.get("accessionNumber", [])
    docs = recent.get("primaryDocument", [])
    accepted = recent.get("acceptanceDateTime", [])
    cutoff = datetime.now(UTC).date() - timedelta(days=days)
    important_forms = {"8-K", "10-Q", "10-K", "6-K", "S-1", "S-3", "424B4", "SC 13D", "SC 13G", "DEF 14A"}

    items: list[NewsItem] = []
    for i, form in enumerate(forms):
        if form not in important_forms:
            continue
        try:
            filing_date = datetime.fromisoformat(dates[i]).date()
        except Exception:
            continue
        if filing_date < cutoff:
            continue
        accession_no_dash = accessions[i].replace("-", "")
        cik_no_zeros = str(int(cik))
        url = f"https://www.sec.gov/Archives/edgar/data/{cik_no_zeros}/{accession_no_dash}/{docs[i]}"
        published = _safe_dt(accepted[i] if i < len(accepted) else dates[i])
        company_name = data.get("name", ticker)
        items.append(
            NewsItem(
                ticker=ticker,
                headline=f"{company_name} presentó {form} ante la SEC",
                summary=f"Filing oficial {form}. Debe revisarse el documento para identificar el evento material y sus cifras.",
                source="SEC EDGAR",
                url=url,
                published_at=published,
                provider="sec",
                category="filing",
                form_type=form,
            )
        )
    return items


def fetch_news_for_ticker(ticker: str, days: int = 2) -> list[NewsItem]:
    combined: list[NewsItem] = []
    # SEC recibe una ventana un poco mayor porque los filings son menos frecuentes.
    combined.extend(fetch_sec_filings(ticker, days=max(days, 7)))
    try:
        combined.extend(fetch_finnhub_news(ticker, days=days))
    except Exception:
        pass
    if not any(item.provider == "finnhub" for item in combined):
        combined.extend(fetch_yfinance_news(ticker, days=max(days, 3)))

    seen: set[str] = set()
    deduped: list[NewsItem] = []
    for item in sorted(combined, key=lambda x: x.published_at, reverse=True):
        key = (item.url or item.headline).lower().strip()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return deduped
