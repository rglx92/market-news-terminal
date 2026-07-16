from __future__ import annotations

import json
import os
import re

from models import MarketSnapshot, NewsAnalysis, NewsItem
from scoring import macro_regime_score, rule_based_analysis, source_quality


def _snapshot_dict(snapshot: MarketSnapshot | None):
    return snapshot.model_dump() if snapshot else None


def _clean_error(exc: Exception) -> str:
    text = re.sub(r"\s+", " ", str(exc)).strip()
    # Nunca incluir claves o cuerpos enormes en la interfaz.
    return f"{exc.__class__.__name__}: {text[:320]}"


def analyze_with_ai(
    news: NewsItem,
    company_snapshot: MarketSnapshot | None,
    spy_snapshot: MarketSnapshot | None,
    macro_context: dict,
    relationships: dict,
) -> tuple[NewsAnalysis | None, str | None]:
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        return None, "OPENAI_API_KEY no está configurada."

    try:
        from openai import OpenAI

        timeout_seconds = float(os.getenv("OPENAI_TIMEOUT_SECONDS", "45"))
        client = OpenAI(api_key=api_key, timeout=timeout_seconds, max_retries=1)
        model = os.getenv("OPENAI_MODEL", "gpt-5.6").strip() or "gpt-5.6"
        relationship_context = relationships.get(news.ticker, {})
        macro_score, macro_confidence, macro_evidence = macro_regime_score(macro_context)
        payload = {
            "news": news.model_dump(mode="json"),
            "company_market_snapshot": _snapshot_dict(company_snapshot),
            "spy_market_snapshot": _snapshot_dict(spy_snapshot),
            "macro_context": {k: v.model_dump() for k, v in macro_context.items()},
            "macro_regime": {
                "score": macro_score,
                "confidence": macro_confidence,
                "evidence": macro_evidence,
            },
            "known_relationships": relationship_context,
        }
        system = """
Eres un analista de catalizadores bursátiles. Evalúa la noticia con disciplina probabilística.
El campo news.ticker ya es el ticker primario atribuido por un filtro determinista; no lo sustituyas
sin evidencia explícita. Usa requested_ticker, mentioned_tickers, relevance_score y relevance_reason
para detectar si el feed original era indirecto. Penaliza listas, resúmenes generales y titulares que
mencionan muchas compañías. Distingue siempre: (1) impacto fundamental para la empresa primaria,
(2) impacto material sobre SPY y (3) si el mercado probablemente ya lo descontó. Una noticia de una
empresa pequeña normalmente tiene impacto SPY cercano a cero. Una noticia favorable para una empresa
puede ser negativa para un competidor. Un filing SEC sin contenido detallado tiene alta calidad de
fuente, pero dirección cercana a neutral salvo evidencia del evento material. No inventes cifras.
Los puntajes van de -100 a 100. La confianza debe caer cuando faltan cifras, contexto, relevancia o
confirmación. affected_tickers debe incluir primero news.ticker. Responde en español.
""".strip()
        response = client.responses.parse(
            model=model,
            input=[
                {"role": "system", "content": system},
                {"role": "user", "content": json.dumps(payload, ensure_ascii=False, default=str)},
            ],
            text_format=NewsAnalysis,
        )
        parsed = response.output_parsed
        if parsed is None:
            return None, "La API respondió sin un objeto estructurado."
        if news.ticker not in parsed.affected_tickers:
            parsed.affected_tickers.insert(0, news.ticker)
        parsed.affected_tickers = list(dict.fromkeys(parsed.affected_tickers))
        return parsed, None
    except Exception as exc:
        return None, _clean_error(exc)


def analyze_news(
    news: NewsItem,
    company_snapshot: MarketSnapshot | None,
    spy_snapshot: MarketSnapshot | None,
    macro_context: dict,
    relationships: dict,
) -> tuple[NewsAnalysis, str, str | None]:
    ai_result, ai_error = analyze_with_ai(
        news, company_snapshot, spy_snapshot, macro_context, relationships
    )
    if ai_result is not None:
        ai_result.source_quality = source_quality(news.source, news.url)
        # Limita la confianza de IA cuando la atribución determinista es débil.
        ai_result.confidence = min(
            ai_result.confidence,
            max(35, int(45 + news.relevance_score * 0.55)),
        )
        return ai_result, "ai", None
    return rule_based_analysis(news, relationships), "rules", ai_error
