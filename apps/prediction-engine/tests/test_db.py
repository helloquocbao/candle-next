"""
Unit tests cho db.py — dac biet la duong loi (DB khong ket noi duoc phai
tra ve None, khong duoc raise va lam crash service) va serialization JSONB
cho model_params_history. Chua tung co test nao cho module nay.

Chạy: cd apps/prediction-engine && pytest

Khong can Postgres thuc — get_connection() duoc monkeypatch hoac psycopg2.connect
duoc gia lap.
"""

import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import db as db_module  # noqa: E402


@pytest.fixture(autouse=True)
def _reset_connection_cache():
    """Tranh 1 test lam ro connection cache anh huong test khac."""
    db_module._connection = None
    yield
    db_module._connection = None


class FakeCursor:
    def __init__(self, fetch_result=None, raise_on_execute=None):
        self.fetch_result = fetch_result
        self.raise_on_execute = raise_on_execute
        self.executed = None

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return False

    def execute(self, query, values):
        if self.raise_on_execute is not None:
            raise self.raise_on_execute
        self.executed = (query, values)

    def fetchone(self):
        return self.fetch_result


class FakeConnection:
    def __init__(self, cursor):
        self._cursor = cursor
        self.closed = 0

    def cursor(self):
        return self._cursor


class FakeTrackedPairsCursor:
    def __init__(self, rows):
        self.rows = rows

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return False

    def execute(self, query, values=None):
        pass

    def fetchall(self):
        return self.rows


def _sample_prediction_row():
    return {
        "symbol": "BTCUSDT",
        "interval": "1m",
        "target_time": "2026-01-01T00:01:00",
        "predicted_open": 100.0,
        "predicted_high": 101.0,
        "predicted_low": 99.0,
        "predicted_close": 100.5,
        "confidence": 0.8,
        "model_version": "baseline-ema-v1",
    }


def test_insert_prediction_returns_id_on_success(monkeypatch):
    cursor = FakeCursor(fetch_result=(42,))
    monkeypatch.setattr(db_module, "get_connection", lambda: FakeConnection(cursor))

    result = db_module.insert_prediction(_sample_prediction_row())

    assert result == 42


def test_insert_prediction_returns_none_when_connection_fails(monkeypatch):
    def boom():
        raise RuntimeError("connection refused")

    monkeypatch.setattr(db_module, "get_connection", boom)

    result = db_module.insert_prediction(_sample_prediction_row())

    assert result is None


def test_insert_prediction_returns_none_when_execute_fails(monkeypatch):
    cursor = FakeCursor(raise_on_execute=RuntimeError("syntax error"))
    monkeypatch.setattr(db_module, "get_connection", lambda: FakeConnection(cursor))

    result = db_module.insert_prediction(_sample_prediction_row())

    assert result is None


def test_insert_accuracy_writes_open_time(monkeypatch):
    cursor = FakeCursor(fetch_result=(9,))
    monkeypatch.setattr(db_module, "get_connection", lambda: FakeConnection(cursor))

    result = db_module.insert_accuracy(
        {
            "prediction_id": 1,
            "symbol": "BTCUSDT",
            "interval": "1d",
            "actual_close": 100.0,
            "predicted_close": 100.5,
            "error_pct": 0.5,
            "accuracy_pct": 99.5,
            "open_time": "2026-01-01T00:00:00+00:00",
        }
    )

    assert result == 9
    _query, values = cursor.executed
    assert values[-1] == "2026-01-01T00:00:00+00:00"


def test_upsert_kline_executes_insert_with_expected_values(monkeypatch):
    cursor = FakeCursor()
    monkeypatch.setattr(db_module, "get_connection", lambda: FakeConnection(cursor))

    db_module.upsert_kline(
        "BTCUSDT", "1m", 1700000000000, 100.0, 101.0, 99.0, 100.5, 12.5, 1700000059999
    )

    _query, values = cursor.executed
    assert values == ("BTCUSDT", "1m", 1700000000000, 100.0, 101.0, 99.0, 100.5, 12.5, 1700000059999)


def test_insert_accuracy_returns_none_when_connection_fails(monkeypatch):
    def boom():
        raise RuntimeError("connection refused")

    monkeypatch.setattr(db_module, "get_connection", boom)

    result = db_module.insert_accuracy(
        {
            "prediction_id": 1,
            "symbol": "BTCUSDT",
            "interval": "1m",
            "actual_close": 100.0,
            "predicted_close": 100.5,
            "error_pct": 0.5,
            "accuracy_pct": 99.5,
        }
    )

    assert result is None


def test_insert_model_params_history_serializes_params_as_json(monkeypatch):
    cursor = FakeCursor(fetch_result=(7,))
    monkeypatch.setattr(db_module, "get_connection", lambda: FakeConnection(cursor))

    result = db_module.insert_model_params_history(
        {"symbol": "BTCUSDT", "params": {"ema_span": 10, "lookback": 50}, "avg_accuracy": 99.5}
    )

    assert result == 7
    _query, values = cursor.executed
    assert values[0] == "BTCUSDT"
    assert json.loads(values[1]) == {"ema_span": 10, "lookback": 50}
    assert values[2] == 99.5


def test_insert_model_params_history_returns_none_when_connection_fails(monkeypatch):
    def boom():
        raise RuntimeError("connection refused")

    monkeypatch.setattr(db_module, "get_connection", boom)

    result = db_module.insert_model_params_history(
        {"symbol": "BTCUSDT", "params": {"ema_span": 10, "lookback": 50}, "avg_accuracy": None}
    )

    assert result is None


def test_get_connection_reuses_cached_open_connection(monkeypatch):
    fake_conn = FakeConnection(None)
    db_module._connection = fake_conn

    assert db_module.get_connection() is fake_conn


def test_get_connection_opens_new_connection_via_psycopg2(monkeypatch):
    class FakeConn2:
        def __init__(self):
            self.autocommit = False
            self.closed = 0

    created = {}

    def fake_connect(dsn):
        created["dsn"] = dsn
        return FakeConn2()

    monkeypatch.setattr(db_module.psycopg2, "connect", fake_connect)
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@localhost/db")

    conn = db_module.get_connection()

    assert created["dsn"] == "postgresql://user:pass@localhost/db"
    assert conn.autocommit is True


def test_get_tracked_pairs_returns_symbol_interval_dicts(monkeypatch):
    cursor = FakeTrackedPairsCursor(rows=[("BTCUSDT", "1m"), ("ETHUSDT", "1m")])
    monkeypatch.setattr(db_module, "get_connection", lambda: FakeConnection(cursor))

    result = db_module.get_tracked_pairs()

    assert result == [
        {"symbol": "BTCUSDT", "interval": "1m"},
        {"symbol": "ETHUSDT", "interval": "1m"},
    ]


def test_get_recent_klines_reverses_desc_rows_to_ascending(monkeypatch):
    from datetime import datetime, timezone

    t2 = datetime(2026, 1, 1, 0, 2, tzinfo=timezone.utc)
    t1 = datetime(2026, 1, 1, 0, 1, tzinfo=timezone.utc)
    # DB tra ve DESC (moi -> cu).
    cursor = FakeTrackedPairsCursor(
        rows=[(t2, 102, 103, 101, 102.5, 20.0), (t1, 101, 102, 100, 101.5, 10.0)]
    )
    monkeypatch.setattr(db_module, "get_connection", lambda: FakeConnection(cursor))

    result = db_module.get_recent_klines("BTCUSDT", "1m", limit=2)

    assert result == [
        {
            "openTime": t1.isoformat(),
            "open": 101.0,
            "high": 102.0,
            "low": 100.0,
            "close": 101.5,
            "volume": 10.0,
            "isClosed": True,
        },
        {
            "openTime": t2.isoformat(),
            "open": 102.0,
            "high": 103.0,
            "low": 101.0,
            "close": 102.5,
            "volume": 20.0,
            "isClosed": True,
        },
    ]


def test_get_recent_klines_returns_empty_list_when_no_history(monkeypatch):
    cursor = FakeTrackedPairsCursor(rows=[])
    monkeypatch.setattr(db_module, "get_connection", lambda: FakeConnection(cursor))

    result = db_module.get_recent_klines("BTCUSDT", "1m")

    assert result == []


def test_get_connection_opens_new_connection_when_cached_one_is_closed(monkeypatch):
    class FakeConn2:
        def __init__(self):
            self.autocommit = False
            self.closed = 0

    stale_conn = FakeConnection(None)
    stale_conn.closed = 1  # da bi dong (vd server restart) -> phai tao moi.
    db_module._connection = stale_conn

    fresh = FakeConn2()
    monkeypatch.setattr(db_module.psycopg2, "connect", lambda dsn: fresh)
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@localhost/db")

    conn = db_module.get_connection()

    assert conn is fresh
