from __future__ import annotations

import os
import re
from collections import defaultdict
from functools import lru_cache
from datetime import UTC, datetime, timedelta
from difflib import SequenceMatcher
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

import requests

try:
    import yfinance as yf
except ImportError:  # permite ejecutar pruebas unitarias sin dependencias de red
    yf = None

from models import NewsItem


TIMEOUT = 20

# Alias conservadores. Evitamos usar símbolos cortos como palabras normales (por ejemplo PL)
# porque generan muchos falsos positivos.
COMPANY_ALIASES: dict[str, tuple[str, ...]] = {
    "SPY": ("s&p 500", "s&p500", "spdr s&p 500", "sp 500"),
    "QQQ": ("nasdaq 100", "invesco qqq"),
    "IWM": ("russell 2000", "ishares russell 2000"),
    "SPCX": ("spacex", "starlink"),
    "RKLB": ("rocket lab",),
    "ASTS": ("ast spacemobile", "ast space mobile"),
    "PL": ("planet labs",),
    "LUNR": ("intuitive machines",),
    "IRDM": ("iridium communications", "iridium"),
    "NVDA": ("nvidia",),
    "AMD": ("advanced micro devices",),
    "AVGO": ("broadcom",),
    "TSM": ("tsmc", "taiwan semiconductor"),
    "MU": ("micron", "micron technology"),
    "SNDK": ("sandisk", "san disk"),
    "MRVL": ("marvell", "marvell technology"),
    "MSFT": ("microsoft",),
    "AAPL": ("apple",),
    "AMZN": ("amazon",),
    "META": ("meta platforms", "facebook", "instagram"),
    "GOOGL": ("alphabet", "google"),
    "TSLA": ("tesla",),
    "NFLX": ("netflix",),
    "ORCL": ("oracle",),
    "CRM": ("salesforce",),
    "INTC": ("intel",),
    "ARM": ("arm holdings",),
    "SMCI": ("super micro computer", "supermicro"),
    "BA": ("boeing",),
    "LMT": ("lockheed martin",),
    "NOC": ("northrop grumman",),
    "RTX": ("rtx corp", "raytheon"),
}

GENERIC_PATTERNS = (
    r"\bstocks? to watch\b",
    r"\bstocks? that (?:explain|moved|move|are moving)\b",
    r"\btop (?:midday |premarket |after-hours )?(?:gainers|decliners|movers)\b",
    r"\bbiggest (?:gainers|decliners|movers)\b",
    r"\bmarket (?:today|update|wrap|recap)\b",
    r"\bstock market (?:today|news|update)\b",
    r"\bsector update\b",
    r"\bdow jones futures\b",
    r"\bpremarket movers\b",
    r"\bmidday movers\b",
    r"\band more stocks\b",
    r"\bwhy these stocks\b",
    r"\bwhat you need to know\b",
)

MACRO_PATTERNS = (
    r"\bfederal reserve\b",
    r"\bthe fed\b",
    r"\bcpi\b",
    r"\bpce\b",
    r"\binflation\b",
    r"\bjobs report\b",
    r"\bpayrolls\b",
    r"\bunemployment\b",
    r"\bgdp\b",
    r"\btreasury yields?\b",
    r"\binterest rates?\b",
    r"\btariffs?\b",
    r"\bs&p 500\b",
    r"\bwall street\b",
)

TRACKING_QUERY_PREFIXES = ("utm_", "guccounter", "guce_referrer", "soc_src", "soc_trk")


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


def _normalize_text(value: str) -> str:
    value = value.lower().replace("’", "'")
    value = re.sub(r"[^a-z0-9$&+.' -]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def _canonical_url(url: str) -> str:
    if not url:
        return ""
    try:
        parsed = urlparse(url)
        clean_query = [
            (k, v)
            for k, v in parse_qsl(parsed.query, keep_blank_values=True)
            if not k.lower().startswith(TRACKING_QUERY_PREFIXES)
        ]
        path = parsed.path.rstrip("/") or "/"
        return urlunparse(
            (
                parsed.scheme.lower(),
                parsed.netloc.lower().removeprefix("www."),
                path,
                "",
                urlencode(clean_query),
                "",
            )
        )
    except Exception:
        return url.strip().lower()


def _ticker_symbol_mentions(raw_text: str, ticker: str) -> bool:
    # Símbolos se aceptan solo si están en mayúsculas, con $ o entre paréntesis.
    patterns = (
        rf"(?<![A-Z0-9])\${re.escape(ticker)}(?![A-Z0-9])",
        rf"\({re.escape(ticker)}\)",
        rf"(?<![A-Z0-9]){re.escape(ticker)}(?=\s+(?:stock|shares|earnings|revenue|price|falls|rises|jumps|drops)\b)",
    )
    return any(re.search(pattern, raw_text) for pattern in patterns)


def extract_mentioned_tickers(headline: str, summary: str = "") -> tuple[list[str], list[str]]:
    raw_headline = headline or ""
    raw_all = f"{headline or ''} {summary or ''}"
    head = _normalize_text(raw_headline)
    all_text = _normalize_text(raw_all)
    headline_mentions: list[str] = []
    all_mentions: list[str] = []

    for ticker, aliases in COMPANY_ALIASES.items():
        in_head = any(re.search(rf"(?<!\w){re.escape(alias)}(?!\w)", head) for alias in aliases)
        in_all = any(re.search(rf"(?<!\w){re.escape(alias)}(?!\w)", all_text) for alias in aliases)
        in_head = in_head or _ticker_symbol_mentions(raw_headline, ticker)
        in_all = in_all or _ticker_symbol_mentions(raw_all, ticker)
        if in_head:
            headline_mentions.append(ticker)
        if in_all:
            all_mentions.append(ticker)

    return list(dict.fromkeys(headline_mentions)), list(dict.fromkeys(all_mentions))


def _starts_with_alias(headline: str, ticker: str) -> bool:
    text = _normalize_text(headline)
    aliases = COMPANY_ALIASES.get(ticker, ())
    return any(text.startswith(alias) or text.startswith(f"why {alias}") for alias in aliases)


def _is_generic_article(headline: str) -> bool:
    text = _normalize_text(headline)
    return any(re.search(pattern, text) for pattern in GENERIC_PATTERNS)


def _is_macro_article(headline: str, summary: str = "") -> bool:
    text = _normalize_text(f"{headline} {summary}")
    return any(re.search(pattern, text) for pattern in MACRO_PATTERNS)


def attribute_news_item(item: NewsItem) -> NewsItem:
    requested = (item.requested_ticker or item.ticker).upper()
    headline_mentions, all_mentions = extract_mentioned_tickers(item.headline, item.summary)
    broad = _is_generic_article(item.headline)
    macro = _is_macro_article(item.headline, item.summary)

    primary = requested
    score = 50
    reason = "La fuente devolvió la noticia para el ticker consultado."

    if item.provider == "sec":
        primary = requested
        score = 100
        reason = "Filing oficial de la compañía consultada."
    elif len(headline_mentions) == 1:
        primary = headline_mentions[0]
        score = 96 if primary != requested else 94
        reason = "Una sola compañía aparece explícitamente en el titular."
    elif len(headline_mentions) > 1:
        if requested in headline_mentions and _starts_with_alias(item.headline, requested):
            primary = requested
            score = 86
            reason = "El titular comienza con la compañía consultada y menciona entidades relacionadas."
        elif requested in headline_mentions and not broad:
            primary = requested
            score = 72
            reason = "La compañía consultada aparece explícitamente, pero comparte el titular con otras."
        else:
            primary = headline_mentions[0]
            score = 52
            reason = "El titular menciona varias compañías sin un sujeto inequívoco."
    elif len(all_mentions) == 1 and not broad:
        primary = all_mentions[0]
        score = 78 if primary != requested else 74
        reason = "Una sola compañía aparece explícitamente en el contenido disponible."
    elif requested == "SPY" and macro:
        primary = "SPY"
        score = 82
        reason = "Noticia macro o de mercado amplio con impacto directo sobre SPY."
    elif item.provider == "finnhub":
        primary = requested
        score = 68
        reason = "Noticia de company-news sin mención inequívoca en el titular."
    else:
        primary = requested
        score = 48
        reason = "La relación depende del feed agregado y no está explícita en el titular."

    if broad:
        score -= 28
        reason += " Penalizada por ser un resumen/lista de múltiples acciones."
    if len(all_mentions) >= 4:
        score -= 15
        reason += " Penalizada por mencionar demasiadas compañías."
    if requested == "SPY" and primary != "SPY":
        reason += f" Se reasignó de SPY a {primary}; SPY era solo el feed de origen."
    if primary not in all_mentions and item.provider != "sec" and not macro:
        score -= 5

    return item.model_copy(
        update={
            "ticker": primary,
            "requested_ticker": requested,
            "mentioned_tickers": all_mentions,
            "relevance_score": max(0, min(100, score)),
            "relevance_reason": reason,
            "is_broad_article": broad,
        }
    )


def _headline_similarity(a: str, b: str) -> float:
    na = _normalize_text(a)
    nb = _normalize_text(b)
    if not na or not nb:
        return 0.0
    seq = SequenceMatcher(None, na, nb).ratio()
    ta, tb = set(na.split()), set(nb.split())
    jaccard = len(ta & tb) / max(1, len(ta | tb))
    return max(seq, jaccard)


def dedupe_news(items: list[NewsItem]) -> list[NewsItem]:
    # Conserva la versión con mayor relevancia, luego mejor proveedor/fuente.
    provider_rank = {"sec": 4, "finnhub": 3, "yfinance": 2}
    ordered = sorted(
        items,
        key=lambda x: (
            x.relevance_score,
            provider_rank.get(x.provider, 1),
            x.published_at,
        ),
        reverse=True,
    )
    kept: list[NewsItem] = []
    seen_urls: set[str] = set()

    for item in ordered:
        canonical = _canonical_url(item.url)
        if canonical and canonical in seen_urls:
            continue
        duplicate = False
        for existing in kept:
            hours = abs((item.published_at - existing.published_at).total_seconds()) / 3600
            if hours <= 48 and _headline_similarity(item.headline, existing.headline) >= 0.88:
                duplicate = True
                break
        if duplicate:
            continue
        kept.append(item)
        if canonical:
            seen_urls.add(canonical)

    return sorted(kept, key=lambda x: x.published_at, reverse=True)


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
                requested_ticker=ticker,
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
    if yf is None:
        return []
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
                requested_ticker=ticker,
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
            "SEC_USER_AGENT", "MarketNewsTerminal/0.2 contact@example.com"
        ),
        "Accept-Encoding": "gzip, deflate",
    }


@lru_cache(maxsize=1)
def _company_ticker_map() -> dict[str, str]:
    response = requests.get(
        "https://www.sec.gov/files/company_tickers.json",
        headers=_sec_headers(),
        timeout=TIMEOUT,
    )
    response.raise_for_status()
    mapping: dict[str, str] = {}
    for row in response.json().values():
        symbol = str(row.get("ticker", "")).upper()
        if symbol:
            mapping[symbol] = str(row["cik_str"]).zfill(10)
    return mapping


def _ticker_to_cik(ticker: str) -> str | None:
    target = ticker.upper().replace("-", ".")
    return _company_ticker_map().get(target)


def fetch_sec_filings(ticker: str, days: int = 7) -> list[NewsItem]:
    if ticker.upper() in {"SPY", "QQQ", "IWM"} or ticker.startswith("^"):
        return []
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
                requested_ticker=ticker,
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
    combined.extend(fetch_sec_filings(ticker, days=max(days, 7)))
    try:
        combined.extend(fetch_finnhub_news(ticker, days=days))
    except Exception:
        pass
    if not any(item.provider == "finnhub" for item in combined):
        combined.extend(fetch_yfinance_news(ticker, days=max(days, 3)))
    attributed = [attribute_news_item(item) for item in combined]
    return dedupe_news(attributed)


def fetch_news_for_watchlist(
    tickers: list[str],
    days: int = 2,
    max_per_ticker: int = 4,
    minimum_relevance: int = 60,
) -> list[NewsItem]:
    raw: list[NewsItem] = []
    for ticker in tickers:
        raw.extend(fetch_news_for_ticker(ticker, days=days))

    unique = dedupe_news(raw)
    filtered = [item for item in unique if item.relevance_score >= minimum_relevance]

    grouped: defaultdict[str, list[NewsItem]] = defaultdict(list)
    for item in filtered:
        grouped[item.ticker].append(item)

    selected: list[NewsItem] = []
    for ticker, group in grouped.items():
        group.sort(key=lambda x: (x.relevance_score, x.published_at), reverse=True)
        selected.extend(group[:max_per_ticker])

    return sorted(
        selected,
        key=lambda x: (x.relevance_score, x.published_at),
        reverse=True,
    )
