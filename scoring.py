from __future__ import annotations

import re
from urllib.parse import urlparse

from models import MarketSnapshot, NewsAnalysis, NewsItem


POSITIVE_TERMS = {
    "beats": 16,
    "beat expectations": 18,
    "record revenue": 18,
    "raises guidance": 20,
    "contract": 12,
    "wins": 7,
    "major government contract": 12,
    "award": 10,
    "approval": 14,
    "successful launch": 15,
    "profit": 8,
    "partnership": 7,
    "buyback": 14,
    "dividend increase": 12,
    "supera expectativas": 18,
    "eleva guía": 20,
    "contrato": 12,
    "gana": 7,
    "contrato gubernamental importante": 12,
    "aprobación": 14,
    "lanzamiento exitoso": 15,
}
NEGATIVE_TERMS = {
    "misses": -16,
    "cuts guidance": -22,
    "offering": -14,
    "dilution": -22,
    "investigation": -13,
    "lawsuit": -10,
    "recall": -12,
    "failed launch": -20,
    "downgrade": -10,
    "bankruptcy": -45,
    "restatement": -20,
    "no alcanza": -16,
    "reduce guía": -22,
    "dilución": -22,
    "investigación": -13,
    "demanda": -10,
    "lanzamiento fallido": -20,
}

MACRO_POSITIVE = {
    "inflation cools": 18,
    "cpi below": 18,
    "rate cut": 16,
    "dovish": 14,
    "jobs soften": 8,
    "inflación baja": 18,
    "recorte de tasas": 16,
}
MACRO_NEGATIVE = {
    "inflation rises": -18,
    "cpi above": -18,
    "rate hike": -18,
    "hawkish": -14,
    "tariff": -10,
    "war": -15,
    "inflación sube": -18,
    "subida de tasas": -18,
    "arancel": -10,
}

MEGACAP_PROXY = {"AAPL", "MSFT", "NVDA", "AMZN", "META", "GOOGL", "GOOG", "AVGO", "TSLA"}


def clamp(value: float, low: int = 0, high: int = 100) -> int:
    return int(max(low, min(high, round(value))))


def source_quality(source: str, url: str = "") -> int:
    text = f"{source} {urlparse(url).netloc}".lower()
    if "sec.gov" in text or "sec edgar" in text:
        return 98
    if any(x in text for x in ["investor relations", "businesswire", "globenewswire", "prnewswire"]):
        return 88
    if any(x in text for x in ["reuters", "bloomberg", "associated press", "apnews", "wsj", "ft.com", "financial times"]):
        return 93
    if any(x in text for x in ["cnbc", "marketwatch", "barrons", "fortune"]):
        return 82
    if any(x in text for x in ["yahoo", "finnhub"]):
        return 72
    if any(x in text for x in ["reddit", "stocktwits", "x.com", "twitter"]):
        return 35
    return 60


def rule_based_analysis(news: NewsItem, relationships: dict) -> NewsAnalysis:
    text = f"{news.headline} {news.summary}".lower()
    score = 0
    evidence: list[str] = []
    for phrase, weight in POSITIVE_TERMS.items():
        if phrase in text:
            score += weight
            evidence.append(f"Se detectó catalizador positivo: {phrase}.")
    for phrase, weight in NEGATIVE_TERMS.items():
        if phrase in text:
            score += weight
            evidence.append(f"Se detectó riesgo negativo: {phrase}.")

    spy_score = 0
    for phrase, weight in MACRO_POSITIVE.items():
        if phrase in text:
            spy_score += weight
            evidence.append(f"Catalizador macro favorable: {phrase}.")
    for phrase, weight in MACRO_NEGATIVE.items():
        if phrase in text:
            spy_score += weight
            evidence.append(f"Catalizador macro desfavorable: {phrase}.")

    event_type = "other"
    event_patterns = {
        "earnings": r"earnings|revenue|eps|resultados|ingresos",
        "guidance": r"guidance|outlook|forecast|guía|perspectiva",
        "contract": r"contract|award|contrato|adjudic",
        "launch": r"launch|rocket|lanzamiento|cohete",
        "regulation": r"regulat|antitrust|regulación|antimonopolio",
        "legal": r"lawsuit|court|investigation|demanda|tribunal|investigación",
        "financing": r"debt|bond|financing|deuda|bonos|financiamiento",
        "dilution": r"offering|dilution|secondary|emisión|dilución",
        "m_and_a": r"acquire|merger|acquisition|adquisición|fusión",
        "management": r"ceo|cfo|resign|director ejecutivo|renuncia",
        "analyst_action": r"upgrade|downgrade|price target|mejora de recomendación|rebaja",
    }
    if news.provider == "sec":
        event_type = "sec_filing"
    else:
        for candidate, pattern in event_patterns.items():
            if re.search(pattern, text):
                event_type = candidate
                break

    quality = source_quality(news.source, news.url)
    if news.provider == "sec":
        score += 4  # Importancia, no dirección. Mantener ajuste pequeño.
    score = max(-100, min(100, score))
    if score >= 55:
        direction = "muy_bullish"
    elif score >= 15:
        direction = "bullish"
    elif score <= -55:
        direction = "muy_bearish"
    elif score <= -15:
        direction = "bearish"
    else:
        direction = "neutral"

    related = relationships.get(news.ticker, {})
    affected = [news.ticker]
    if abs(score) >= 15:
        affected.extend(related.get("sector_peers", [])[:4])

    directness = "directa"
    if event_type in {"macro", "fed", "economic_data"}:
        directness = "macro"
    elif news.ticker == "SPY":
        directness = "macro"
    elif affected[1:]:
        directness = "sectorial"

    if news.ticker in MEGACAP_PROXY and abs(score) >= 15:
        spy_score += int(score * 0.16)

    confidence = clamp(35 + quality * 0.42 + min(abs(score), 30) * 0.45)
    novelty = 65 if news.provider in {"sec", "finnhub"} else 50
    already_priced = 45
    positives = [e for e in evidence if "positivo" in e or "favorable" in e]
    risks = [e for e in evidence if "negativo" in e or "desfavorable" in e]
    if not evidence:
        evidence = ["No hubo suficientes términos cuantificables; requiere revisión humana o modo IA."]

    return NewsAnalysis(
        direction=direction,
        company_impact=score,
        spy_impact=max(-100, min(100, spy_score)),
        confidence=confidence,
        source_quality=quality,
        novelty=novelty,
        already_priced_probability=already_priced,
        event_type=event_type,
        horizon="días",
        directness=directness,
        affected_tickers=list(dict.fromkeys(affected)),
        thesis=(
            "La clasificación proviene de reglas y del tipo de catalizador; úsala como filtro inicial, no como pronóstico."
        ),
        positives=positives or ["No se identificó una ventaja cuantificable con reglas."],
        risks=risks or ["El titular puede omitir cifras, condiciones o expectativas ya descontadas."],
        evidence=evidence,
    )


def market_confirmation(impact: int, company: MarketSnapshot | None, spy: MarketSnapshot | None) -> int:
    confirmation = 50.0
    sign = 1 if impact > 0 else -1 if impact < 0 else 0
    if company and company.change_1d_pct is not None and sign:
        aligned = company.change_1d_pct * sign
        confirmation += max(-20, min(20, aligned * 4))
    if company and company.relative_volume_20d is not None:
        confirmation += max(-5, min(12, (company.relative_volume_20d - 1) * 10))
    if spy and spy.change_1d_pct is not None and sign:
        confirmation += max(-8, min(8, spy.change_1d_pct * sign * 3))
    return clamp(confirmation)


def trade_quality_score(
    analysis: NewsAnalysis,
    company: MarketSnapshot | None,
    spy: MarketSnapshot | None,
) -> tuple[int, int]:
    confirmation = market_confirmation(analysis.company_impact, company, spy)
    score = (
        abs(analysis.company_impact) * 0.30
        + analysis.confidence * 0.20
        + analysis.source_quality * 0.12
        + analysis.novelty * 0.10
        + confirmation * 0.22
        + (100 - analysis.already_priced_probability) * 0.06
    )

    # Penaliza perseguir una reacción extrema del mismo signo.
    if company and company.change_1d_pct is not None and analysis.company_impact != 0:
        aligned_move = company.change_1d_pct * (1 if analysis.company_impact > 0 else -1)
        if aligned_move > 8:
            score -= min(18, (aligned_move - 8) * 1.5)
    return clamp(score), confirmation
