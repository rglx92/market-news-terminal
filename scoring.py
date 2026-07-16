from __future__ import annotations

import re
from urllib.parse import urlparse

from models import MarketSnapshot, NewsAnalysis, NewsItem, ScoredAnalysis


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
    "raises price target": 12,
    "price target raised": 12,
    "doubles from here": 10,
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
    "price target cut": -12,
    "delay": -9,
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


def signed_clamp(value: float) -> int:
    return int(max(-100, min(100, round(value))))



def _contains_phrase(text: str, phrase: str) -> bool:
    # Evita falsos positivos como "war" dentro de "award".
    pattern = rf"(?<![\w]){re.escape(phrase)}(?![\w])"
    return re.search(pattern, text) is not None

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
        if _contains_phrase(text, phrase):
            score += weight
            evidence.append(f"Se detectó catalizador positivo: {phrase}.")
    for phrase, weight in NEGATIVE_TERMS.items():
        if _contains_phrase(text, phrase):
            score += weight
            evidence.append(f"Se detectó riesgo negativo: {phrase}.")

    spy_score = 0
    for phrase, weight in MACRO_POSITIVE.items():
        if _contains_phrase(text, phrase):
            spy_score += weight
            evidence.append(f"Catalizador macro favorable: {phrase}.")
    for phrase, weight in MACRO_NEGATIVE.items():
        if _contains_phrase(text, phrase):
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
        "analyst_action": r"upgrade|downgrade|price target|wall street firm|analyst|mejora de recomendación|rebaja",
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
        score += 4  # Importancia, no dirección.

    # Las listas/resúmenes generales no deben generar señales fuertes.
    if news.is_broad_article:
        score *= 0.45
    # Relevancia baja reduce la magnitud incluso si algún término coincide.
    relevance_factor = 0.55 + news.relevance_score / 220
    score *= min(1.0, relevance_factor)
    score = signed_clamp(score)

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
    if abs(score) >= 15 and news.relevance_score >= 70:
        affected.extend(related.get("sector_peers", [])[:4])

    directness = "directa"
    if news.ticker == "SPY" or event_type in {"macro", "fed", "economic_data"}:
        directness = "macro"
    elif news.requested_ticker and news.requested_ticker != news.ticker:
        directness = "indirecta"
    elif affected[1:]:
        directness = "sectorial"

    if news.ticker in MEGACAP_PROXY and abs(score) >= 15:
        spy_score += int(score * 0.16)
    elif news.ticker != "SPY":
        # Noticias de empresas pequeñas normalmente no mueven SPY de forma material.
        spy_score = int(spy_score * 0.5)

    confidence = clamp(
        20
        + quality * 0.30
        + news.relevance_score * 0.32
        + min(abs(score), 30) * 0.35
        - (12 if news.is_broad_article else 0)
    )
    novelty = clamp((70 if news.provider in {"sec", "finnhub"} else 52) + (news.relevance_score - 60) * 0.2)
    already_priced = 48
    positives = [e for e in evidence if "positivo" in e or "favorable" in e]
    risks = [e for e in evidence if "negativo" in e or "desfavorable" in e]
    if not evidence:
        evidence = ["No hubo suficientes términos cuantificables; requiere revisión humana o modo IA."]
    evidence.append(f"Relevancia de atribución: {news.relevance_score}/100. {news.relevance_reason}")

    return NewsAnalysis(
        direction=direction,
        company_impact=score,
        spy_impact=signed_clamp(spy_score),
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
    relevance_score: int = 100,
) -> tuple[int, int]:
    confirmation = market_confirmation(analysis.company_impact, company, spy)
    score = (
        abs(analysis.company_impact) * 0.28
        + analysis.confidence * 0.18
        + analysis.source_quality * 0.11
        + analysis.novelty * 0.09
        + confirmation * 0.20
        + relevance_score * 0.10
        + (100 - analysis.already_priced_probability) * 0.04
    )

    if company and company.change_1d_pct is not None and analysis.company_impact != 0:
        aligned_move = company.change_1d_pct * (1 if analysis.company_impact > 0 else -1)
        if aligned_move > 8:
            score -= min(18, (aligned_move - 8) * 1.5)
    return clamp(score), confirmation


def macro_regime_score(macro: dict[str, MarketSnapshot]) -> tuple[int, int, list[str]]:
    """Convierte índices, volatilidad, bonos y dólar en un sesgo risk-on/risk-off."""
    specs = {
        "SPY": (12.0, 25.0, "SPY"),
        "QQQ": (10.0, 25.0, "QQQ"),
        "IWM": (6.0, 16.0, "IWM"),
        "VIX": (-3.0, 25.0, "VIX"),
        "US10Y": (-2.0, 12.0, "US10Y"),
        "DXY": (-2.0, 12.0, "DXY"),
    }
    total = 0.0
    used = 0
    evidence: list[str] = []
    for key, (multiplier, cap, label) in specs.items():
        snap = macro.get(key)
        change = None if snap is None else snap.change_1d_pct
        if change is None:
            continue
        contribution = max(-cap, min(cap, change * multiplier))
        total += contribution
        used += 1
        effect = "favorable" if contribution > 1 else "desfavorable" if contribution < -1 else "neutral"
        evidence.append(f"{label} {change:+.2f}%: efecto {effect} ({contribution:+.1f}).")
    confidence = clamp(used / len(specs) * 100)
    return signed_clamp(total), confidence, evidence


def aggregate_spy_bias(
    items: list[ScoredAnalysis],
    macro: dict[str, MarketSnapshot],
) -> tuple[float, float, int, list[str]]:
    macro_score, macro_conf, macro_evidence = macro_regime_score(macro)
    weighted_sum = 0.0
    weight_total = 0.0
    directness_weight = {"macro": 1.0, "directa": 0.75, "sectorial": 0.55, "indirecta": 0.35}
    for item in items:
        a = item.analysis
        weight = (
            max(0.1, a.confidence / 100)
            * max(0.1, item.news.relevance_score / 100)
            * directness_weight.get(a.directness, 0.5)
        )
        if abs(a.spy_impact) < 3:
            weight *= 0.35
        weighted_sum += a.spy_impact * weight
        weight_total += weight
    news_score = weighted_sum / weight_total if weight_total else 0.0
    news_conf = min(100.0, (weight_total / max(1, len(items))) * 100) if items else 0.0

    if items and macro_conf > 0:
        combined = macro_score * 0.62 + news_score * 0.38
        confidence = macro_conf * 0.60 + news_conf * 0.40
    elif macro_conf > 0:
        combined, confidence = float(macro_score), float(macro_conf)
    else:
        combined, confidence = float(news_score), float(news_conf)
    return float(max(-100, min(100, combined))), float(max(0, min(100, confidence))), macro_score, macro_evidence
