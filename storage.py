from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from models import ScoredAnalysis


DB_PATH = Path(__file__).with_name("market_news.db")


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS analyses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            ticker TEXT NOT NULL,
            published_at TEXT NOT NULL,
            headline TEXT NOT NULL,
            url TEXT,
            provider TEXT,
            mode TEXT,
            company_impact INTEGER,
            spy_impact INTEGER,
            trade_quality INTEGER,
            confidence INTEGER,
            payload_json TEXT NOT NULL,
            UNIQUE(ticker, headline, published_at)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS outcomes (
            analysis_id INTEGER PRIMARY KEY,
            return_1d REAL,
            return_3d REAL,
            return_5d REAL,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(analysis_id) REFERENCES analyses(id)
        )
        """
    )
    conn.commit()
    return conn


def save_analysis(item: ScoredAnalysis) -> None:
    conn = connect()
    try:
        conn.execute(
            """
            INSERT OR IGNORE INTO analyses (
                ticker, published_at, headline, url, provider, mode,
                company_impact, spy_impact, trade_quality, confidence, payload_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                item.news.ticker,
                item.news.published_at.isoformat(),
                item.news.headline,
                item.news.url,
                item.news.provider,
                item.mode,
                item.analysis.company_impact,
                item.analysis.spy_impact,
                item.trade_quality,
                item.analysis.confidence,
                json.dumps(item.model_dump(mode="json"), ensure_ascii=False),
            ),
        )
        conn.commit()
    finally:
        conn.close()


def recent_history(limit: int = 200):
    conn = connect()
    try:
        return conn.execute(
            """
            SELECT created_at, ticker, published_at, headline, mode,
                   company_impact, spy_impact, trade_quality, confidence
            FROM analyses ORDER BY id DESC LIMIT ?
            """,
            (limit,),
        ).fetchall()
    finally:
        conn.close()


def pending_outcomes(limit: int = 100):
    conn = connect()
    try:
        return conn.execute(
            """
            SELECT a.id, a.ticker, a.published_at, a.company_impact
            FROM analyses a
            LEFT JOIN outcomes o ON o.analysis_id = a.id
            WHERE o.analysis_id IS NULL
            ORDER BY a.id ASC LIMIT ?
            """,
            (limit,),
        ).fetchall()
    finally:
        conn.close()


def upsert_outcome(analysis_id: int, return_1d, return_3d, return_5d) -> None:
    conn = connect()
    try:
        conn.execute(
            """
            INSERT INTO outcomes (analysis_id, return_1d, return_3d, return_5d)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(analysis_id) DO UPDATE SET
              return_1d=excluded.return_1d,
              return_3d=excluded.return_3d,
              return_5d=excluded.return_5d,
              updated_at=CURRENT_TIMESTAMP
            """,
            (analysis_id, return_1d, return_3d, return_5d),
        )
        conn.commit()
    finally:
        conn.close()


def calibration_rows(limit: int = 500):
    conn = connect()
    try:
        return conn.execute(
            """
            SELECT a.ticker, a.company_impact, a.confidence, a.trade_quality,
                   o.return_1d, o.return_3d, o.return_5d
            FROM analyses a
            JOIN outcomes o ON o.analysis_id = a.id
            ORDER BY a.id DESC LIMIT ?
            """,
            (limit,),
        ).fetchall()
    finally:
        conn.close()
