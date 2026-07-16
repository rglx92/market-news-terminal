from __future__ import annotations

import html
import json
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from dotenv import load_dotenv

from analyzer import analyze_news
from market_data import get_macro_context, get_snapshot
from models import ScoredAnalysis
from news_sources import fetch_news_for_ticker
from outcomes import update_pending_outcomes
from scoring import trade_quality_score
from storage import calibration_rows, recent_history, save_analysis


load_dotenv()
BASE_DIR = Path(__file__).parent
RELATIONSHIPS = json.loads((BASE_DIR / "relationships.json").read_text(encoding="utf-8"))

st.set_page_config(
    page_title="MNT · Market News Terminal",
    page_icon="✦",
    layout="wide",
    initial_sidebar_state="expanded",
)


def inject_theme() -> None:
    st.markdown(
        """
        <style>
        :root {
            --bg: #06100d;
            --panel: rgba(11, 25, 21, 0.88);
            --panel-2: rgba(14, 32, 27, 0.78);
            --line: rgba(115, 255, 184, 0.14);
            --text: #edf8f2;
            --muted: #8ca89c;
            --green: #4cf59a;
            --green-2: #28c97a;
            --red: #ff6474;
            --amber: #f6c95b;
            --cyan: #5ce1e6;
        }

        html, body, [class*="css"] {
            font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
        }

        .stApp {
            color: var(--text);
            background:
                radial-gradient(circle at 16% 0%, rgba(29, 132, 84, 0.20), transparent 34%),
                radial-gradient(circle at 92% 8%, rgba(246, 201, 91, 0.09), transparent 26%),
                linear-gradient(160deg, #030906 0%, #07110e 47%, #081813 100%);
        }

        [data-testid="stHeader"] {
            background: transparent;
        }

        [data-testid="stToolbar"] {
            right: 1rem;
        }

        [data-testid="stSidebar"] {
            background: linear-gradient(180deg, rgba(5, 15, 11, 0.98), rgba(8, 21, 17, 0.98));
            border-right: 1px solid var(--line);
        }

        [data-testid="stSidebar"] > div:first-child {
            padding-top: 1.25rem;
        }

        .block-container {
            max-width: 1580px;
            padding-top: 1.35rem;
            padding-bottom: 3rem;
        }

        .mnt-hero {
            position: relative;
            overflow: hidden;
            padding: 1.45rem 1.55rem;
            margin-bottom: 1rem;
            border: 1px solid rgba(76, 245, 154, 0.18);
            border-radius: 22px;
            background:
                linear-gradient(115deg, rgba(13, 35, 28, 0.96), rgba(7, 20, 16, 0.88)),
                radial-gradient(circle at 80% 0%, rgba(76, 245, 154, 0.24), transparent 35%);
            box-shadow: 0 24px 80px rgba(0, 0, 0, 0.28), inset 0 1px 0 rgba(255,255,255,0.04);
        }

        .mnt-hero::after {
            content: "";
            position: absolute;
            width: 240px;
            height: 240px;
            border-radius: 50%;
            right: -80px;
            top: -115px;
            background: rgba(76, 245, 154, 0.08);
            filter: blur(2px);
        }

        .hero-row {
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 1rem;
        }

        .brand-kicker {
            color: var(--amber);
            font-size: 0.72rem;
            font-weight: 800;
            letter-spacing: 0.18em;
            text-transform: uppercase;
            margin-bottom: 0.35rem;
        }

        .brand-title {
            margin: 0;
            font-size: clamp(1.65rem, 3vw, 2.6rem);
            line-height: 1.02;
            font-weight: 850;
            letter-spacing: -0.045em;
        }

        .brand-title span { color: var(--green); }

        .brand-subtitle {
            margin-top: 0.65rem;
            max-width: 820px;
            color: var(--muted);
            font-size: 0.95rem;
            line-height: 1.55;
        }

        .live-pill {
            display: inline-flex;
            align-items: center;
            gap: 0.45rem;
            white-space: nowrap;
            padding: 0.55rem 0.8rem;
            border: 1px solid rgba(76, 245, 154, 0.23);
            border-radius: 999px;
            background: rgba(76, 245, 154, 0.07);
            color: #b9ffd8;
            font-size: 0.74rem;
            font-weight: 800;
            letter-spacing: 0.08em;
        }

        .live-dot {
            width: 8px;
            height: 8px;
            border-radius: 50%;
            background: var(--green);
            box-shadow: 0 0 0 5px rgba(76, 245, 154, 0.09), 0 0 18px rgba(76, 245, 154, 0.75);
        }

        .section-label {
            margin: 1.1rem 0 0.7rem;
            color: #d9eee4;
            font-size: 0.76rem;
            font-weight: 800;
            letter-spacing: 0.14em;
            text-transform: uppercase;
        }

        .metric-shell {
            min-height: 116px;
            padding: 1rem 1rem 0.9rem;
            border: 1px solid var(--line);
            border-radius: 17px;
            background: linear-gradient(145deg, rgba(15, 34, 28, 0.90), rgba(8, 22, 18, 0.86));
            box-shadow: inset 0 1px 0 rgba(255,255,255,0.035), 0 14px 34px rgba(0,0,0,0.18);
        }

        .metric-top {
            display: flex;
            justify-content: space-between;
            align-items: center;
            gap: 0.5rem;
        }

        .metric-label {
            color: var(--muted);
            font-size: 0.72rem;
            font-weight: 760;
            letter-spacing: 0.09em;
            text-transform: uppercase;
        }

        .metric-value {
            margin-top: 0.48rem;
            color: var(--text);
            font-size: 1.55rem;
            font-weight: 820;
            letter-spacing: -0.035em;
        }

        .metric-foot {
            margin-top: 0.36rem;
            color: var(--muted);
            font-size: 0.74rem;
            line-height: 1.35;
        }

        .tone-positive { color: var(--green); }
        .tone-negative { color: var(--red); }
        .tone-neutral { color: var(--amber); }

        .score-pill {
            display: inline-flex;
            align-items: center;
            padding: 0.28rem 0.5rem;
            border-radius: 999px;
            font-size: 0.67rem;
            font-weight: 850;
        }

        .pill-positive { color: #b7ffd5; background: rgba(76,245,154,0.09); border: 1px solid rgba(76,245,154,0.18); }
        .pill-negative { color: #ffbdc4; background: rgba(255,100,116,0.09); border: 1px solid rgba(255,100,116,0.18); }
        .pill-neutral { color: #ffe2a0; background: rgba(246,201,91,0.09); border: 1px solid rgba(246,201,91,0.18); }

        .news-card {
            padding: 1.05rem 1.15rem;
            margin-bottom: 0.85rem;
            border: 1px solid var(--line);
            border-left-width: 3px;
            border-radius: 15px;
            background: linear-gradient(135deg, rgba(13, 31, 26, 0.92), rgba(8, 21, 17, 0.85));
            box-shadow: 0 12px 30px rgba(0,0,0,0.16);
        }

        .news-card.positive { border-left-color: var(--green); }
        .news-card.negative { border-left-color: var(--red); }
        .news-card.neutral { border-left-color: var(--amber); }

        .news-meta {
            display: flex;
            flex-wrap: wrap;
            align-items: center;
            gap: 0.45rem;
            margin-bottom: 0.58rem;
        }

        .ticker-badge {
            padding: 0.24rem 0.48rem;
            color: #07110d;
            background: var(--amber);
            border-radius: 7px;
            font-size: 0.68rem;
            font-weight: 900;
            letter-spacing: 0.06em;
        }

        .tiny-chip {
            padding: 0.22rem 0.45rem;
            border-radius: 7px;
            color: #a9c3b7;
            background: rgba(255,255,255,0.035);
            border: 1px solid rgba(255,255,255,0.055);
            font-size: 0.65rem;
            font-weight: 700;
        }

        .news-headline {
            color: #f0faf5;
            font-size: 1rem;
            line-height: 1.43;
            font-weight: 760;
        }

        .news-thesis {
            margin-top: 0.55rem;
            color: var(--muted);
            font-size: 0.82rem;
            line-height: 1.48;
        }

        .score-grid {
            display: grid;
            grid-template-columns: repeat(4, minmax(0, 1fr));
            gap: 0.65rem;
            margin-top: 0.85rem;
        }

        .score-cell {
            padding: 0.65rem 0.7rem;
            border-radius: 10px;
            background: rgba(255,255,255,0.026);
            border: 1px solid rgba(255,255,255,0.045);
        }

        .score-cell-label {
            color: var(--muted);
            font-size: 0.62rem;
            font-weight: 750;
            text-transform: uppercase;
            letter-spacing: 0.08em;
        }

        .score-cell-value {
            margin-top: 0.25rem;
            font-size: 0.94rem;
            font-weight: 850;
        }

        .empty-state {
            padding: 2.2rem 1.4rem;
            border: 1px dashed rgba(76,245,154,0.2);
            border-radius: 18px;
            text-align: center;
            background: rgba(11, 28, 23, 0.55);
        }

        .empty-icon {
            font-size: 2.1rem;
            margin-bottom: 0.5rem;
        }

        .empty-title {
            color: #edf8f2;
            font-size: 1.1rem;
            font-weight: 800;
        }

        .empty-copy {
            max-width: 620px;
            margin: 0.45rem auto 0;
            color: var(--muted);
            font-size: 0.84rem;
            line-height: 1.55;
        }

        .sidebar-brand {
            padding: 0.15rem 0 1rem;
        }

        .sidebar-logo {
            color: var(--amber);
            font-size: 1.28rem;
            font-weight: 900;
            letter-spacing: -0.03em;
        }

        .sidebar-copy {
            color: var(--muted);
            font-size: 0.73rem;
            line-height: 1.45;
            margin-top: 0.25rem;
        }

        div[data-testid="stButton"] > button {
            min-height: 2.8rem;
            border: 1px solid rgba(76,245,154,0.2);
            border-radius: 12px;
            font-weight: 800;
            letter-spacing: 0.01em;
            transition: transform 120ms ease, box-shadow 120ms ease, border-color 120ms ease;
        }

        div[data-testid="stButton"] > button:hover {
            transform: translateY(-1px);
            border-color: rgba(76,245,154,0.42);
            box-shadow: 0 10px 24px rgba(0,0,0,0.20);
        }

        div[data-testid="stButton"] > button[kind="primary"] {
            color: #04100a;
            background: linear-gradient(100deg, #48ed94, #91ffc4);
            border-color: transparent;
        }

        div[data-testid="stTextArea"] textarea,
        div[data-testid="stTextInput"] input {
            color: #eaf7f0;
            background: rgba(255,255,255,0.035);
            border-color: rgba(255,255,255,0.08);
            border-radius: 11px;
        }

        div[data-testid="stSlider"] [data-baseweb="slider"] {
            padding-top: 0.25rem;
        }

        [data-testid="stMetric"] {
            padding: 0.85rem 0.95rem;
            border: 1px solid var(--line);
            border-radius: 14px;
            background: var(--panel);
        }

        [data-testid="stMetricLabel"] { color: var(--muted); }
        [data-testid="stMetricValue"] { color: #f2fbf6; }

        [data-testid="stDataFrame"] {
            border: 1px solid var(--line);
            border-radius: 14px;
            overflow: hidden;
        }

        .stTabs [data-baseweb="tab-list"] {
            gap: 0.35rem;
            padding: 0.3rem;
            border: 1px solid var(--line);
            border-radius: 13px;
            background: rgba(7, 19, 15, 0.78);
        }

        .stTabs [data-baseweb="tab"] {
            height: 2.65rem;
            padding: 0 1rem;
            border-radius: 9px;
            color: var(--muted);
            font-weight: 750;
        }

        .stTabs [aria-selected="true"] {
            color: #dffbec !important;
            background: rgba(76,245,154,0.10) !important;
        }

        [data-testid="stExpander"] {
            border: 1px solid var(--line);
            border-radius: 13px;
            background: rgba(10, 25, 20, 0.82);
        }

        hr { border-color: rgba(255,255,255,0.07); }

        @media (max-width: 760px) {
            .hero-row { align-items: flex-start; flex-direction: column; }
            .score-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
            .block-container { padding-left: 0.8rem; padding-right: 0.8rem; }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def esc(value: object) -> str:
    return html.escape(str(value or ""))


def fmt_pct(value: float | None) -> str:
    return "—" if value is None else f"{value:+.2f}%"


def score_tone(value: float, neutral_band: float = 10) -> tuple[str, str]:
    if value > neutral_band:
        return "positive", "tone-positive"
    if value < -neutral_band:
        return "negative", "tone-negative"
    return "neutral", "tone-neutral"


def label_direction(value: int) -> str:
    if value >= 55:
        return "Muy bullish"
    if value >= 15:
        return "Bullish"
    if value <= -55:
        return "Muy bearish"
    if value <= -15:
        return "Bearish"
    return "Neutral"


def render_header(watchlist_count: int, mode_label: str) -> None:
    st.markdown(
        f"""
        <section class="mnt-hero">
          <div class="hero-row">
            <div>
              <div class="brand-kicker">MNT · MARKET INTELLIGENCE</div>
              <h1 class="brand-title">Noticias que se convierten en <span>señales</span>.</h1>
              <div class="brand-subtitle">
                Evalúa impacto fundamental, efecto probable sobre SPY, confirmación de mercado
                y calidad del trade. Cada conclusión conserva su evidencia y después se calibra
                contra el movimiento real.
              </div>
            </div>
            <div class="live-pill"><span class="live-dot"></span>{esc(mode_label)} · {watchlist_count} tickers</div>
          </div>
        </section>
        """,
        unsafe_allow_html=True,
    )


def render_metric_card(label: str, value: str, foot: str, score: float | None = None) -> None:
    pill = ""
    value_class = ""
    if score is not None:
        tone, tone_class = score_tone(score)
        value_class = tone_class
        pill_label = "BULL" if tone == "positive" else "BEAR" if tone == "negative" else "MIXED"
        pill = f'<span class="score-pill pill-{tone}">{pill_label}</span>'
    st.markdown(
        f"""
        <div class="metric-shell">
          <div class="metric-top"><div class="metric-label">{esc(label)}</div>{pill}</div>
          <div class="metric-value {value_class}">{esc(value)}</div>
          <div class="metric-foot">{esc(foot)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_news_card(item: ScoredAnalysis) -> None:
    analysis = item.analysis
    news = item.news
    tone, tone_class = score_tone(analysis.company_impact)
    published = news.published_at.strftime("%d %b · %I:%M %p")
    st.markdown(
        f"""
        <article class="news-card {tone}">
          <div class="news-meta">
            <span class="ticker-badge">{esc(news.ticker)}</span>
            <span class="score-pill pill-{tone}">{esc(label_direction(analysis.company_impact))}</span>
            <span class="tiny-chip">{esc(analysis.event_type.replace('_', ' '))}</span>
            <span class="tiny-chip">{esc(analysis.horizon)}</span>
            <span class="tiny-chip">{esc(news.source or news.provider)}</span>
            <span class="tiny-chip">{esc(published)}</span>
          </div>
          <div class="news-headline">{esc(news.headline)}</div>
          <div class="news-thesis">{esc(analysis.thesis)}</div>
          <div class="score-grid">
            <div class="score-cell">
              <div class="score-cell-label">Empresa</div>
              <div class="score-cell-value {tone_class}">{analysis.company_impact:+d}</div>
            </div>
            <div class="score-cell">
              <div class="score-cell-label">Impacto SPY</div>
              <div class="score-cell-value">{analysis.spy_impact:+d}</div>
            </div>
            <div class="score-cell">
              <div class="score-cell-label">Trade</div>
              <div class="score-cell-value">{item.trade_quality}</div>
            </div>
            <div class="score-cell">
              <div class="score-cell-label">Confianza</div>
              <div class="score-cell-value">{analysis.confidence}%</div>
            </div>
          </div>
        </article>
        """,
        unsafe_allow_html=True,
    )


def render_macro_cards(macro: dict) -> None:
    st.markdown('<div class="section-label">Market pulse</div>', unsafe_allow_html=True)
    cols = st.columns(6)
    for col, key in zip(cols, ["SPY", "QQQ", "IWM", "VIX", "US10Y", "DXY"]):
        snapshot = macro.get(key)
        price = "—" if snapshot is None or snapshot.price is None else f"{snapshot.price:,.2f}"
        change = None if snapshot is None else snapshot.change_1d_pct
        with col:
            render_metric_card(
                key,
                price,
                f"Sesión: {fmt_pct(change)}",
                change,
            )


def spy_gauge(value: float, confidence: float) -> go.Figure:
    value = max(-100, min(100, value))
    fig = go.Figure(
        go.Indicator(
            mode="gauge+number",
            value=value,
            number={"suffix": "/100", "font": {"size": 31, "color": "#edf8f2"}},
            title={
                "text": f"Sesgo agregado · confianza {confidence:.0f}%",
                "font": {"size": 13, "color": "#8ca89c"},
            },
            gauge={
                "axis": {
                    "range": [-100, 100],
                    "tickwidth": 1,
                    "tickcolor": "rgba(255,255,255,0.18)",
                    "tickfont": {"color": "#8ca89c"},
                },
                "bar": {"color": "#4cf59a" if value >= 0 else "#ff6474", "thickness": 0.26},
                "bgcolor": "rgba(255,255,255,0.02)",
                "borderwidth": 0,
                "steps": [
                    {"range": [-100, -20], "color": "rgba(255,100,116,0.15)"},
                    {"range": [-20, 20], "color": "rgba(246,201,91,0.09)"},
                    {"range": [20, 100], "color": "rgba(76,245,154,0.13)"},
                ],
                "threshold": {
                    "line": {"color": "#f6c95b", "width": 3},
                    "thickness": 0.72,
                    "value": 0,
                },
            },
        )
    )
    fig.update_layout(
        height=310,
        margin=dict(l=35, r=35, t=55, b=20),
        paper_bgcolor="rgba(0,0,0,0)",
        font={"color": "#edf8f2"},
    )
    return fig


def analysis_scatter(filtered: pd.DataFrame) -> go.Figure:
    chart_df = filtered.head(35).copy()
    chart_df["Etiqueta"] = chart_df["Ticker"] + " — " + chart_df["Titular"].str.slice(0, 64)
    chart_df["Sesgo"] = chart_df["Empresa"].apply(
        lambda value: "Bullish" if value > 10 else "Bearish" if value < -10 else "Neutral"
    )
    fig = px.scatter(
        chart_df,
        x="Empresa",
        y="Trade",
        size="Confianza",
        color="Sesgo",
        hover_name="Etiqueta",
        hover_data=["SPY", "Confirmación", "Fuente", "Modo"],
        color_discrete_map={"Bullish": "#4cf59a", "Bearish": "#ff6474", "Neutral": "#f6c95b"},
    )
    fig.add_vline(x=0, line_width=1, line_dash="dot", line_color="rgba(255,255,255,0.25)")
    fig.update_traces(marker={"line": {"width": 1, "color": "rgba(255,255,255,0.20)"}})
    fig.update_layout(
        height=485,
        margin=dict(l=20, r=20, t=20, b=20),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(8,22,18,0.60)",
        font={"color": "#dcece4"},
        xaxis={
            "title": "Impacto fundamental",
            "gridcolor": "rgba(255,255,255,0.055)",
            "zeroline": False,
            "range": [-105, 105],
        },
        yaxis={
            "title": "Calidad del trade",
            "gridcolor": "rgba(255,255,255,0.055)",
            "range": [0, 105],
        },
        legend={"title": "", "orientation": "h", "y": 1.08, "x": 0},
    )
    return fig


inject_theme()

with st.sidebar:
    st.markdown(
        """
        <div class="sidebar-brand">
          <div class="sidebar-logo">MNT ✦</div>
          <div class="sidebar-copy">Market News Terminal<br>Radar diario de catalizadores.</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.markdown("### Configuración")
    watchlist_raw = st.text_area(
        "Watchlist",
        value="SPY, SPCX, RKLB, ASTS, PL, LUNR, NVDA, MSFT, AAPL, AMZN, META, GOOGL",
        help="Símbolos separados por coma.",
        height=118,
    )
    lookback_days = st.slider("Días de noticias", 1, 7, 2)
    max_news = st.slider("Máximo por ticker", 1, 10, 4)
    minimum_quality = st.slider("Calidad mínima del trade", 0, 100, 35)
    run = st.button("✦ Analizar noticias", type="primary", use_container_width=True)
    calibrate = st.button("Actualizar resultados reales", use_container_width=True)
    st.divider()
    st.caption(
        "IA avanzada: `OPENAI_API_KEY` · Cobertura adicional: `FINNHUB_API_KEY` · "
        "Sin claves funciona con SEC, yfinance y reglas locales."
    )

watchlist = list(dict.fromkeys(x.strip().upper() for x in watchlist_raw.split(",") if x.strip()))
mode_label = "AI READY" if st.session_state.get("scored_items") else "STANDBY"
render_header(len(watchlist), mode_label)

if calibrate:
    with st.spinner("Calculando retornos posteriores aproximados..."):
        result = update_pending_outcomes(150)
    st.sidebar.success(f"Actualizados: {result['updated']} · Pendientes: {result['skipped']}")

if run:
    progress = st.progress(0, text="Cargando contexto de mercado...")
    macro = get_macro_context()
    spy_snapshot = macro.get("SPY") or get_snapshot("SPY")

    rows: list[dict] = []
    scored_items: list[ScoredAnalysis] = []
    total = max(1, len(watchlist))

    for idx, ticker in enumerate(watchlist):
        progress.progress(idx / total, text=f"Analizando {ticker}...")
        company_snapshot = spy_snapshot if ticker == "SPY" else get_snapshot(ticker)
        news_items = fetch_news_for_ticker(ticker, days=lookback_days)[:max_news]
        for news in news_items:
            analysis, mode = analyze_news(
                news,
                company_snapshot,
                spy_snapshot,
                macro,
                RELATIONSHIPS,
            )
            trade_quality, confirmation = trade_quality_score(
                analysis, company_snapshot, spy_snapshot
            )
            scored = ScoredAnalysis(
                news=news,
                analysis=analysis,
                trade_quality=trade_quality,
                market_confirmation=confirmation,
                company_snapshot=company_snapshot,
                spy_snapshot=spy_snapshot,
                mode=mode,
            )
            save_analysis(scored)
            scored_items.append(scored)
            rows.append(
                {
                    "Hora": news.published_at,
                    "Ticker": ticker,
                    "Titular": news.headline,
                    "Empresa": analysis.company_impact,
                    "SPY": analysis.spy_impact,
                    "Trade": trade_quality,
                    "Confirmación": confirmation,
                    "Confianza": analysis.confidence,
                    "Fuente": news.source,
                    "Modo": mode,
                }
            )

    progress.progress(1.0, text="Análisis terminado.")
    st.session_state["scored_items"] = scored_items
    st.session_state["rows"] = rows
    st.session_state["macro"] = macro

rows = st.session_state.get("rows", [])
scored_items: list[ScoredAnalysis] = st.session_state.get("scored_items", [])
macro = st.session_state.get("macro", {})

if not rows:
    st.markdown('<div class="section-label">Centro de mando</div>', unsafe_allow_html=True)
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        render_metric_card("Impacto empresa", "−100 → +100", "Distingue catalizador real de ruido.")
    with c2:
        render_metric_card("Módulo SPY", "Macro + mercado", "Fed, índices, bonos, VIX y dólar.")
    with c3:
        render_metric_card("Trade quality", "0 → 100", "Evita confundir buena noticia con buena entrada.")
    with c4:
        render_metric_card("Calibración", "1d · 3d · 5d", "Compara cada predicción contra el retorno real.")

    st.markdown(
        """
        <div class="empty-state">
          <div class="empty-icon">✦</div>
          <div class="empty-title">Tu radar está listo.</div>
          <div class="empty-copy">
            Ajusta la watchlist en la barra lateral y pulsa <b>Analizar noticias</b>.
            El dashboard ordenará primero los catalizadores con mayor impacto, confirmación y confianza.
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
else:
    df = pd.DataFrame(rows)
    filtered = df[df["Trade"] >= minimum_quality].sort_values(
        ["Trade", "Confianza"], ascending=False
    )

    if macro:
        render_macro_cards(macro)

    st.markdown('<div class="section-label">Resumen de señales</div>', unsafe_allow_html=True)
    bullish = filtered.sort_values("Empresa", ascending=False).iloc[0] if not filtered.empty else None
    bearish = filtered.sort_values("Empresa", ascending=True).iloc[0] if not filtered.empty else None
    spy_bias = float(filtered["SPY"].mean()) if not filtered.empty else 0.0
    high_quality = int((filtered["Trade"] >= 70).sum()) if not filtered.empty else 0

    s1, s2, s3, s4 = st.columns(4)
    with s1:
        render_metric_card(
            "Señal bullish líder",
            "—" if bullish is None else f"{bullish['Ticker']}  {int(bullish['Empresa']):+d}",
            "Sin señales suficientes" if bullish is None else str(bullish["Titular"])[:72],
            None if bullish is None else float(bullish["Empresa"]),
        )
    with s2:
        render_metric_card(
            "Señal bearish líder",
            "—" if bearish is None else f"{bearish['Ticker']}  {int(bearish['Empresa']):+d}",
            "Sin señales suficientes" if bearish is None else str(bearish["Titular"])[:72],
            None if bearish is None else float(bearish["Empresa"]),
        )
    with s3:
        render_metric_card("Sesgo SPY", f"{spy_bias:+.1f}", "Promedio ponderable de noticias filtradas.", spy_bias)
    with s4:
        render_metric_card("Setups ≥ 70", str(high_quality), f"{len(filtered)} noticias superan el filtro actual.")

    radar_tab, news_tab, spy_tab, history_tab = st.tabs(
        ["Radar", "Feed visual", "SPY & macro", "Historial y calibración"]
    )

    with radar_tab:
        if filtered.empty:
            st.info("No hay noticias que superen la calidad mínima seleccionada.")
        else:
            left, right = st.columns([1.35, 1])
            with left:
                st.plotly_chart(analysis_scatter(filtered), use_container_width=True)
            with right:
                top = filtered.head(8).copy()
                top["Señal"] = top["Empresa"].apply(label_direction)
                st.dataframe(
                    top[["Ticker", "Señal", "Trade", "Confianza", "Titular"]],
                    use_container_width=True,
                    hide_index=True,
                    height=485,
                    column_config={
                        "Trade": st.column_config.ProgressColumn(min_value=0, max_value=100),
                        "Confianza": st.column_config.ProgressColumn(min_value=0, max_value=100),
                        "Titular": st.column_config.TextColumn(width="large"),
                    },
                )

            st.markdown('<div class="section-label">Tabla completa</div>', unsafe_allow_html=True)
            st.dataframe(
                filtered,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Empresa": st.column_config.ProgressColumn(min_value=-100, max_value=100),
                    "SPY": st.column_config.ProgressColumn(min_value=-100, max_value=100),
                    "Trade": st.column_config.ProgressColumn(min_value=0, max_value=100),
                    "Confirmación": st.column_config.ProgressColumn(min_value=0, max_value=100),
                    "Confianza": st.column_config.ProgressColumn(min_value=0, max_value=100),
                    "Hora": st.column_config.DatetimeColumn(format="MMM D, h:mm a"),
                    "Titular": st.column_config.TextColumn(width="large"),
                },
            )

    with news_tab:
        ordered = sorted(
            scored_items,
            key=lambda item: (item.trade_quality, item.analysis.confidence),
            reverse=True,
        )
        visible = [item for item in ordered if item.trade_quality >= minimum_quality]
        if not visible:
            st.info("No hay noticias que superen el filtro actual.")
        for item in visible:
            render_news_card(item)
            details_title = f"Evidencia y riesgos · {item.news.ticker} · Trade {item.trade_quality}/100"
            with st.expander(details_title):
                a = item.analysis
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("Fuente", f"{a.source_quality}/100")
                c2.metric("Novedad", f"{a.novelty}/100")
                c3.metric("Ya descontada", f"{a.already_priced_probability}%")
                c4.metric("Confirmación", f"{item.market_confirmation}/100")

                p1, p2 = st.columns(2)
                with p1:
                    st.markdown("**A favor**")
                    for point in a.positives:
                        st.write(f"✓ {point}")
                with p2:
                    st.markdown("**Riesgos**")
                    for point in a.risks:
                        st.write(f"⚠ {point}")

                st.markdown("**Evidencia usada**")
                for point in a.evidence:
                    st.write(f"• {point}")
                st.caption(
                    f"Relación: {a.directness} · Modo: {item.mode} · "
                    f"Afectados: {', '.join(a.affected_tickers)}"
                )
                if item.news.url:
                    st.link_button("Abrir fuente original ↗", item.news.url)

    with spy_tab:
        spy_news = filtered.copy()
        avg_spy = float(spy_news["SPY"].mean()) if not spy_news.empty else 0.0
        avg_conf = float(spy_news["Confianza"].mean()) if not spy_news.empty else 0.0
        left, right = st.columns([0.9, 1.1])
        with left:
            st.plotly_chart(spy_gauge(avg_spy, avg_conf), use_container_width=True)
        with right:
            st.markdown('<div class="section-label">Catalizadores de mayor alcance</div>', unsafe_allow_html=True)
            top_spy = spy_news.reindex(spy_news["SPY"].abs().sort_values(ascending=False).index).head(8)
            if top_spy.empty:
                st.info("No hay catalizadores para SPY bajo el filtro actual.")
            else:
                st.dataframe(
                    top_spy[["Ticker", "SPY", "Confianza", "Titular"]],
                    use_container_width=True,
                    hide_index=True,
                    height=310,
                    column_config={
                        "SPY": st.column_config.ProgressColumn(min_value=-100, max_value=100),
                        "Confianza": st.column_config.ProgressColumn(min_value=0, max_value=100),
                        "Titular": st.column_config.TextColumn(width="large"),
                    },
                )

        st.caption(
            "El sesgo agregado resume las noticias filtradas; no sustituye la lectura del precio, "
            "la amplitud, los rendimientos ni el posicionamiento de opciones."
        )

    with history_tab:
        st.markdown('<div class="section-label">Historial guardado</div>', unsafe_allow_html=True)
        history = recent_history(100)
        if history:
            history_df = pd.DataFrame(
                history,
                columns=[
                    "Guardado", "Ticker", "Publicación", "Titular", "Modo",
                    "Empresa", "SPY", "Trade", "Confianza",
                ],
            )
            st.dataframe(history_df, use_container_width=True, hide_index=True)
        else:
            st.info("Todavía no hay análisis guardados.")

        st.markdown('<div class="section-label">Calibración histórica</div>', unsafe_allow_html=True)
        cal_rows = calibration_rows(500)
        if cal_rows:
            cal = pd.DataFrame(
                cal_rows,
                columns=[
                    "Ticker", "Impacto", "Confianza", "Trade",
                    "Retorno 1d", "Retorno 3d", "Retorno 5d",
                ],
            )
            eligible = cal[cal["Impacto"].abs() >= 15].copy()
            if not eligible.empty:
                metric_cols = st.columns(3)
                for col, horizon in zip(metric_cols, ["Retorno 1d", "Retorno 3d", "Retorno 5d"]):
                    valid = eligible.dropna(subset=[horizon]).copy()
                    with col:
                        if valid.empty:
                            st.metric(horizon.replace("Retorno ", "Dirección "), "—")
                        else:
                            valid["Acierto"] = (valid["Impacto"] * valid[horizon]) > 0
                            accuracy = valid["Acierto"].mean() * 100
                            st.metric(
                                horizon.replace("Retorno ", "Dirección "),
                                f"{accuracy:.1f}%",
                                help=f"{len(valid)} observaciones con |impacto| ≥ 15.",
                            )
                st.dataframe(eligible, use_container_width=True, hide_index=True)
            else:
                st.info("Aún no hay suficientes observaciones con señal direccional.")
        else:
            st.info(
                "Pulsa “Actualizar resultados reales” cuando existan análisis con sesiones posteriores disponibles."
            )

st.markdown(
    """
    <div style="margin-top:2rem;padding-top:1rem;border-top:1px solid rgba(255,255,255,.06);color:#789287;font-size:.72rem;">
      Investigación cuantitativa asistida · Ninguna señal garantiza el movimiento futuro ni constituye asesoría financiera.
    </div>
    """,
    unsafe_allow_html=True,
)
