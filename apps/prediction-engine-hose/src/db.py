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


def insert_ai_signal(row: dict) -> int:
    """
    Ghi 1 tín hiệu AI (DeepSeek, xem ai_advisor.py) vào bảng `ai_signals`
    (market='hose') — audit trail RIÊNG với `predictions`, để sau này đánh
    giá AI có thực sự cải thiện accuracy hay không (so sánh accuracy_log của
    các prediction có model_version chứa "+deepseek" vs không, xem
    infra/db/migrations/006_ai_signals.sql).

    Không tự bắt lỗi ở đây (giống upsert_kline/insert_prediction ở trên) —
    caller (main.py::process_symbol) chịu trách nhiệm try/except quanh lời
    gọi này để 1 lỗi ghi audit không làm chết cả chu kỳ xử lý mã đó.
    """
    query = """
        INSERT INTO ai_signals
            (prediction_id, symbol, interval, market, direction,
             predicted_change_pct, ai_confidence, blended, reasoning)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING id;
    """
    values = (
        row.get("prediction_id"), row["symbol"], row["interval"], MARKET,
        row["direction"], row.get("predicted_change_pct"), row.get("ai_confidence"),
        row.get("blended", True), row.get("reasoning"),
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


def get_recent_klines(symbol: str, interval: str, limit: int = 2000) -> list[dict]:
    """
    Đọc N nến daily HOSE gần nhất từ bảng `klines` (market='hose') — dùng
    bởi training/train_lightgbm.py để lấy lịch sử train/validation. Khác với
    main.py::process_symbol (luôn fetch trực tiếp từ vnstock mỗi chu kỳ),
    hàm này đọc lại dữ liệu ĐÃ được upsert vào DB qua các chu kỳ trước đó —
    phù hợp cho training vì cần nhiều lịch sử hơn HOSE_HISTORY_DAYS hiện tại
    của 1 lần fetch.

    Returns:
        list[dict]: sắp xếp THỜI GIAN TĂNG DẦN (cũ -> mới), có "volume" (cần
        cho features/feature_builder.py::relative_volume).
    """
    query = """
        SELECT open_time, open, high, low, close, volume
        FROM klines
        WHERE symbol = %s AND interval = %s AND market = %s
        ORDER BY open_time DESC
        LIMIT %s
    """
    with _lock:
        with get_connection().cursor() as cur:
            cur.execute(query, (symbol.upper(), interval, MARKET, limit))
            rows = cur.fetchall()

    return [
        {
            "openTime": row[0].isoformat(),
            "open": float(row[1]),
            "high": float(row[2]),
            "low": float(row[3]),
            "close": float(row[4]),
            "volume": float(row[5]),
            "isClosed": True,
        }
        for row in reversed(rows)  # DB trả về DESC (mới -> cũ) -> đảo lại tăng dần
    ]
