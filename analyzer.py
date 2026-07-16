from __future__ import annotations

import json
import os

from models import MarketSnapshot, NewsAnalysis, NewsItem
from scoring import rule_based_analysis, source_quality


def _snapshot_dict(snapshot: MarketSnapshot | None):
    return snapshot.model_dump() if snapshot else None


def analyze_with_ai(
    news: NewsItem,
    company_snapshot: MarketSnapshot | None,
    spy_snapshot: MarketSnapshot | None,
    macro_context: dict,
    relationships: dict,
) -> NewsAnalysis | None:
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        return None

    try:
        from openai import OpenAI

        client = OpenAI(api_key=api_key)
        model = os.getenv("OPENAI_MODEL", "gpt-5.6")
        relationship_context = relationships.get(news.ticker, {})
        payload = {
            "news": news.model_dump(mode="json"),
            "company_market_snapshot": _snapshot_dict(company_snapshot),
            "spy_market_snapshot": _snapshot_dict(spy_snapshot),
            "macro_context": {k: v.model_dump() for k, v in macro_context.items()},
            "known_relationships": relationship_context,
        }
        system = """
Eres un analista de catalizadores bursátiles. Evalúa la noticia con disciplina probabilística.
Distingue siempre entre: (1) impacto fundamental para la empresa, (2) impacto sobre SPY,
y (3) si el mercado probablemente ya lo descontó. No predigas con certeza ni inventes cifras.
Una noticia favorable para una empresa puede ser negativa para un competidor. Un filing SEC sin
contenido detallado debe tener alta calidad de fuente pero dirección cercana a neutral, salvo que
el texto aporte el evento material. Usa solo la evidencia incluida. Los puntajes van de -100 a 100.
La confianza debe caer cuando faltan cifras, contexto o confirmación. Responde en español.
""".strip()
        response = client.responses.parse(
            model=model,
            input=[
                {"role": "system", "content": system},
                {"role": "user", "content": json.dumps(payload, ensure_ascii=False, default=str)},
            ],
            text_format=NewsAnalysis,
        )
        return response.output_parsed
    except Exception:
        return None


def analyze_news(
    news: NewsItem,
    company_snapshot: MarketSnapshot | None,
    spy_snapshot: MarketSnapshot | None,
    macro_context: dict,
    relationships: dict,
) -> tuple[NewsAnalysis, str]:
    ai_result = analyze_with_ai(
        news, company_snapshot, spy_snapshot, macro_context, relationships
    )
    if ai_result is not None:
        # La calidad de fuente se calcula de forma determinista para evitar que el modelo la invente.
        ai_result.source_quality = source_quality(news.source, news.url)
        return ai_result, "ai"
    return rule_based_analysis(news, relationships), "rules"
