from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


Direction = Literal["muy_bullish", "bullish", "neutral", "bearish", "muy_bearish"]
EventType = Literal[
    "earnings",
    "guidance",
    "contract",
    "product",
    "launch",
    "regulation",
    "macro",
    "fed",
    "economic_data",
    "legal",
    "financing",
    "dilution",
    "m_and_a",
    "management",
    "sec_filing",
    "analyst_action",
    "rumor",
    "other",
]
Horizon = Literal["intradía", "días", "semanas", "meses"]


class NewsItem(BaseModel):
    # ticker es el ticker primario atribuido después de depurar la noticia.
    ticker: str
    headline: str
    summary: str = ""
    source: str = ""
    url: str = ""
    published_at: datetime
    provider: str
    category: str = "company"
    form_type: str | None = None

    # Metadatos de precisión y auditoría.
    requested_ticker: str | None = None
    mentioned_tickers: list[str] = Field(default_factory=list)
    relevance_score: int = Field(default=70, ge=0, le=100)
    relevance_reason: str = ""
    is_broad_article: bool = False


class MarketSnapshot(BaseModel):
    ticker: str
    price: float | None = None
    change_1d_pct: float | None = None
    change_5d_pct: float | None = None
    change_20d_pct: float | None = None
    relative_volume_20d: float | None = None
    above_20d_ma: bool | None = None
    above_50d_ma: bool | None = None


class NewsAnalysis(BaseModel):
    direction: Direction
    company_impact: int = Field(ge=-100, le=100)
    spy_impact: int = Field(ge=-100, le=100)
    confidence: int = Field(ge=0, le=100)
    source_quality: int = Field(ge=0, le=100)
    novelty: int = Field(ge=0, le=100)
    already_priced_probability: int = Field(ge=0, le=100)
    event_type: EventType
    horizon: Horizon
    directness: Literal["directa", "indirecta", "sectorial", "macro"]
    affected_tickers: list[str]
    thesis: str
    positives: list[str]
    risks: list[str]
    evidence: list[str]


class ScoredAnalysis(BaseModel):
    news: NewsItem
    analysis: NewsAnalysis
    trade_quality: int = Field(ge=0, le=100)
    market_confirmation: int = Field(ge=0, le=100)
    company_snapshot: MarketSnapshot | None = None
    spy_snapshot: MarketSnapshot | None = None
    mode: Literal["ai", "rules"]
    ai_error: str | None = None
