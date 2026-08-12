"""
Ket noi PostgreSQL/TimescaleDB va cac ham ghi du lieu cho prediction-engine.

Schema tham chieu theo project_technical_spec.md muc 3.2:

    CREATE TABLE predictions (
        id              BIGSERIAL,
        symbol          TEXT NOT NULL,
        interval        TEXT NOT NULL,
        target_time     TIMESTAMPTZ NOT NULL,
        predicted_open  NUMERIC,
        predicted_high  NUMERIC,
        predicted_low   NUMERIC,
        predicted_close NUMERIC,
        confidence      NUMERIC,
        model_version   TEXT,
        created_at      TIMESTAMPTZ DEFAULT now(),
        PRIMARY KEY (id, created_at)
    );

    CREATE TABLE accuracy_log (
        id              BIGSERIAL PRIMARY KEY,
        prediction_id   BIGINT,
        symbol          TEXT,
        interval        TEXT,
        actual_close    NUMERIC,
        predicted_close NUMERIC,
        error_pct       NUMERIC,
        accuracy_pct    NUMERIC,
        evaluated_at    TIMESTAMPTZ DEFAULT now()
    );

    CREATE TABLE model_params_history (
        id           BIGSERIAL PRIMARY KEY,
        symbol       TEXT,
        params       JSONB,
        avg_accuracy NUMERIC,
        updated_at   TIMESTAMPTZ DEFAULT now()
    );
"""

from __future__ import annotations

import json
import logging
import os
import threading
from typing import Any, Optional

import psycopg2

logger = logging.getLogger(__name__)

_connection = None
# psycopg2 khong cho phep 2 query chay dong thoi tren CUNG 1 connection (chi
# 1 request "in flight" moi luc theo giao thuc libpq). Vi mot process gio
# co the chay nhieu PredictionEngine (1 thread/cap symbol-interval, xem
# resolve_tracked_pairs trong main.py), moi thao tac ghi DB deu phai serialize
# qua lock nay de tranh doc/ghi chong cheo tren connection dung chung.
_lock = threading.Lock()


def get_connection():
    """
    Khoi tao (hoac tra ve) connection Postgres/TimescaleDB dung chung cho
    ca service. DATABASE_URL doc tu bien moi truong.

    Dung 1 connection don gian (khong pool) cho baseline MVP — service nay
    chi ghi tuan tu theo tung nen dong, tan suat thap (vd moi phut).
    """
    global _connection

    if _connection is not None and _connection.closed == 0:
        return _connection

    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        logger.warning(
            "[db] Canh bao: bien moi truong DATABASE_URL chua duoc thiet lap. "
            "Cac thao tac ghi DB se that bai cho toi khi duoc cau hinh dung."
        )

    _connection = psycopg2.connect(database_url)
    _connection.autocommit = True
    return _connection


def insert_prediction(pred: dict[str, Any]) -> Optional[int]:
    """
    Ghi 1 ban ghi du doan vao bang `predictions`.

    Args:
        pred: dict can co cac key:
            symbol, interval, target_time (ISO string / datetime),
            predicted_open, predicted_high, predicted_low, predicted_close,
            confidence, model_version

    Returns:
        int | None: id cua ban ghi vua insert, hoac None neu that bai.
    """
    query = """
        INSERT INTO predictions (
            symbol, interval, target_time,
            predicted_open, predicted_high, predicted_low, predicted_close,
            confidence, model_version
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING id;
    """
    values = (
        pred["symbol"],
        pred["interval"],
        pred["target_time"],
        pred["predicted_open"],
        pred["predicted_high"],
        pred["predicted_low"],
        pred["predicted_close"],
        pred["confidence"],
        pred.get("model_version"),
    )

    try:
        with _lock:
            conn = get_connection()
            with conn.cursor() as cur:
                cur.execute(query, values)
                row = cur.fetchone()
                return int(row[0]) if row else None
    except Exception as exc:  # noqa: BLE001 - khong de crash toan bo service
        logger.error(
            "[db] Loi khi ghi prediction vao DB (%s %s %s): %s",
            pred.get("symbol"),
            pred.get("interval"),
            pred.get("target_time"),
            exc,
        )
        return None


def insert_accuracy(row: dict[str, Any]) -> Optional[int]:
    """
    Ghi 1 ban ghi danh gia do chinh xac vao bang `accuracy_log`.

    Args:
        row: dict can co cac key:
            prediction_id, symbol, interval, actual_close, predicted_close,
            error_pct, accuracy_pct, open_time (ISO string cua nen THAT duoc
            danh gia — de frontend ve marker % chinh xac dung vi tri nen)

    Returns:
        int | None: id cua ban ghi vua insert, hoac None neu that bai.
    """
    query = """
        INSERT INTO accuracy_log (
            prediction_id, symbol, interval,
            actual_close, predicted_close, error_pct, accuracy_pct, open_time
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING id;
    """
    values = (
        row.get("prediction_id"),
        row["symbol"],
        row["interval"],
        row["actual_close"],
        row["predicted_close"],
        row["error_pct"],
        row["accuracy_pct"],
        row.get("open_time"),
    )

    try:
        with _lock:
            conn = get_connection()
            with conn.cursor() as cur:
                cur.execute(query, values)
                result = cur.fetchone()
                return int(result[0]) if result else None
    except Exception as exc:  # noqa: BLE001 - khong de crash toan bo service
        logger.error(
            "[db] Loi khi ghi accuracy_log vao DB (%s %s): %s",
            row.get("symbol"),
            row.get("interval"),
            exc,
        )
        return None


def insert_model_params_history(row: dict[str, Any]) -> Optional[int]:
    """
    Ghi 1 ban ghi tham so moi (sau khi Genetic Algorithm toi uu xong) vao
    bang `model_params_history` — audit trail cho vong lap self-learning
    (spec muc 3.2 & 4.4).

    Args:
        row: dict can co cac key:
            symbol, params (dict — se duoc serialize thanh JSONB),
            avg_accuracy (float | None)

    Returns:
        int | None: id cua ban ghi vua insert, hoac None neu that bai.
    """
    query = """
        INSERT INTO model_params_history (symbol, params, avg_accuracy)
        VALUES (%s, %s, %s)
        RETURNING id;
    """
    values = (
        row["symbol"],
        json.dumps(row["params"]),
        row.get("avg_accuracy"),
    )

    try:
        with _lock:
            conn = get_connection()
            with conn.cursor() as cur:
                cur.execute(query, values)
                result = cur.fetchone()
                return int(result[0]) if result else None
    except Exception as exc:  # noqa: BLE001 - khong de crash toan bo service
        logger.error(
            "[db] Loi khi ghi model_params_history vao DB (%s): %s",
            row.get("symbol"),
            exc,
        )
        return None


def insert_ai_signal(row: dict[str, Any]) -> Optional[int]:
    """
    Ghi 1 tin hieu AI (DeepSeek, xem ai_advisor.py) vao bang `ai_signals` —
    audit trail RIENG voi `predictions`/`accuracy_log`, de sau nay co the
    danh gia AI co thuc su cai thien accuracy hay khong (so sanh accuracy_log
    cua cac prediction co model_version chua "+deepseek" vs khong, xem
    infra/db/migrations/006_ai_signals.sql).

    Args:
        row: dict can co cac key:
            prediction_id (id cua ban ghi trong bang `predictions` tuong ung,
                co the None neu insert_prediction that bai truoc do),
            symbol, interval, direction ("up"|"down"|"flat"),
            predicted_change_pct, ai_confidence, blended (bool — co duoc
            dung de blend vao prediction cuoi cung hay chi ghi lai de tham
            khao), reasoning (str | None)

    Returns:
        int | None: id cua ban ghi vua insert, hoac None neu that bai. LOI O
        DAY KHONG duoc anh huong luong du doan chinh (giong tinh than
        insert_accuracy/insert_prediction o tren) — day chi la du lieu audit.
    """
    query = """
        INSERT INTO ai_signals (
            prediction_id, symbol, interval, direction,
            predicted_change_pct, ai_confidence, blended, reasoning
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING id;
    """
    values = (
        row.get("prediction_id"),
        row["symbol"],
        row["interval"],
        row["direction"],
        row.get("predicted_change_pct"),
        row.get("ai_confidence"),
        row.get("blended", True),
        row.get("reasoning"),
    )

    try:
        with _lock:
            conn = get_connection()
            with conn.cursor() as cur:
                cur.execute(query, values)
                result = cur.fetchone()
                return int(result[0]) if result else None
    except Exception as exc:  # noqa: BLE001 - du lieu audit, khong duoc lam chet service
        logger.error(
            "[db] Loi khi ghi ai_signals vao DB (%s %s): %s",
            row.get("symbol"),
            row.get("interval"),
            exc,
        )
        return None


def get_tracked_pairs() -> list[dict[str, str]]:
    """
    Doc danh sach cap symbol/interval dang active tu bang tracked_pairs
    (infra/db/migrations/002_tracked_pairs.sql) — nguon chan ly chung de
    prediction-engine/ingestion-service/api-gateway deu fan-out/hien thi
    dung mot danh sach, khong hardcode rieng moi noi.
    """
    with _lock:
        conn = get_connection()
        with conn.cursor() as cur:
            cur.execute(
                "SELECT symbol, interval FROM tracked_pairs WHERE is_active ORDER BY symbol, interval"
            )
            rows = cur.fetchall()
    return [{"symbol": row[0], "interval": row[1]} for row in rows]


def get_recent_klines(symbol: str, interval: str, limit: int = 200) -> list[dict[str, Any]]:
    """
    Doc N nen da dong gan nhat tu bang `klines` (da duoc ingestion-service
    bootstrap qua REST Binance ngay khi khoi dong) — dung de seed truoc
    buffer in-memory cua PredictionEngine (xem main.py::PredictionEngine.
    seed_from_history), tranh phai cho candle_buffer rong cho toi khi co nen
    THAT dau tien dong sau khi service khoi dong — voi khung gio/ngay/tuan/
    thang, co the mat hang gio/ngay/thang moi co nen dau tien neu khong seed.

    Returns:
        list[dict]: sap xep THOI GIAN TANG DAN (cu -> moi), dung dinh dang
        voi cac phan tu trong candle_buffer (openTime ISO string, open/high/
        low/close/volume, isClosed=True) — co "volume" de dung duoc ca cho
        features/feature_builder.py (can volume tinh relative_volume), khong
        chi rieng cho seed baseline (baseline khong dung volume).
    """
    with _lock:
        conn = get_connection()
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT open_time, open, high, low, close, volume
                FROM klines
                WHERE symbol = %s AND interval = %s
                ORDER BY open_time DESC
                LIMIT %s
                """,
                (symbol, interval, limit),
            )
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
        for row in reversed(rows)  # DB tra ve DESC (moi -> cu) -> dao lai tang dan
    ]


def upsert_kline(
    symbol: str,
    interval: str,
    open_time_ms: int,
    open_: float,
    high: float,
    low: float,
    close: float,
    volume: float,
    close_time_ms: int,
) -> None:
    """
    Ghi (upsert) 1 nen da dong vao bang `klines` — dung boi
    training/backfill_history.py de nap them lich su dai han truc tiep tu
    Binance REST (backfill), TRUOC KHI co du lieu do ingestion-service ghi
    vao qua luong bootstrap/real-time thong thuong. Cung 1 bang, cung khoa
    xung dot (symbol, interval, open_time) nhu apps/ingestion-service/src/db.js
    de khong tao du lieu trung/mau thuan.
    """
    query = """
        INSERT INTO klines (symbol, interval, open_time, open, high, low, close, volume, close_time)
        VALUES (%s, %s, to_timestamp(%s / 1000.0), %s, %s, %s, %s, %s, to_timestamp(%s / 1000.0))
        ON CONFLICT (symbol, interval, open_time) DO UPDATE SET
            open = EXCLUDED.open,
            high = EXCLUDED.high,
            low = EXCLUDED.low,
            close = EXCLUDED.close,
            volume = EXCLUDED.volume,
            close_time = EXCLUDED.close_time;
    """
    values = (symbol, interval, open_time_ms, open_, high, low, close, volume, close_time_ms)

    with _lock:
        conn = get_connection()
        with conn.cursor() as cur:
            cur.execute(query, values)


def close_connection() -> None:
    """Dong connection (dung khi shutdown graceful)."""
    global _connection
    if _connection is not None:
        try:
            _connection.close()
        except Exception as exc:  # noqa: BLE001
            logger.error("[db] Loi khi dong connection: %s", exc)
        finally:
            _connection = None
