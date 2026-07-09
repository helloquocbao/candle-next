"""
Ghi dữ liệu HOSE vào PostgreSQL/TimescaleDB dùng CHUNG với crypto, nhưng
đánh dấu market='hose' để tách biệt (xem migration 005_market_column.sql).

Dùng lại bảng `klines` và `predictions` sẵn có — HOSE chỉ ghi symbol là mã
cổ phiếu (vd FPT) + interval '1d', không đụng dữ liệu crypto (symbol khác
nhau, thêm cột market). KHÔNG sửa code crypto.
"""

from __future__ import annotations

import logging
import os
import threading

import psycopg2

logger = logging.getLogger(__name__)

MARKET = "hose"

_connection = None
_lock = threading.Lock()


def get_connection():
    global _connection
    if _connection is not None and _connection.closed == 0:
        return _connection
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise RuntimeError("[db] DATABASE_URL chưa được thiết lập.")
    _connection = psycopg2.connect(database_url)
    _connection.autocommit = True
    logger.info("[db] Đã kết nối DATABASE_URL (market=%s).", MARKET)
    return _connection


def upsert_kline(kline: dict) -> None:
    """Upsert 1 nến daily HOSE vào bảng klines (market='hose')."""
    query = """
        INSERT INTO klines
            (symbol, interval, open_time, open, high, low, close, volume, close_time, market)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (symbol, interval, open_time)
        DO UPDATE SET
            open = EXCLUDED.open, high = EXCLUDED.high, low = EXCLUDED.low,
            close = EXCLUDED.close, volume = EXCLUDED.volume,
            close_time = EXCLUDED.close_time, market = EXCLUDED.market;
    """
    values = (
        kline["symbol"], kline["interval"], kline["openTime"],
        kline["open"], kline["high"], kline["low"], kline["close"],
        kline["volume"], kline["closeTime"], MARKET,
    )
    with _lock:
        with get_connection().cursor() as cur:
            cur.execute(query, values)


def insert_prediction(pred: dict) -> int:
    """Ghi 1 dòng dự đoán HOSE (market='hose'), trả về id."""
    query = """
        INSERT INTO predictions
            (symbol, interval, target_time, predicted_open, predicted_high,
             predicted_low, predicted_close, confidence, model_version, market)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING id;
    """
    values = (
        pred["symbol"], pred["interval"], pred["target_time"],
        pred["predicted_open"], pred["predicted_high"], pred["predicted_low"],
        pred["predicted_close"], pred["confidence"], pred["model_version"], MARKET,
    )
    with _lock:
        with get_connection().cursor() as cur:
            cur.execute(query, values)
            return cur.fetchone()[0]


def close_connection() -> None:
    global _connection
    if _connection is not None and _connection.closed == 0:
        _connection.close()
    _connection = None
