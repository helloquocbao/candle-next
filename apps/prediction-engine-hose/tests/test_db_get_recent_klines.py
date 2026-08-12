"""
Unit test cho src/db.py::get_recent_klines() — đọc bảng klines lọc
market='hose', đảo thứ tự DESC (DB) -> ASC (caller cần tăng dần thời gian).
Mock hoàn toàn psycopg2 connection/cursor, KHÔNG kết nối Postgres thật.
Tham khảo pattern mock từ apps/prediction-engine/tests/test_db.py, viết lại
đúng schema/module của bản HOSE (db.py chỉ có get_recent_klines/upsert_kline/
insert_prediction/insert_ai_signal, KHÔNG có insert_accuracy/get_tracked_pairs
như bản crypto).

Chạy: cd apps/prediction-engine-hose && python3 -m pytest tests/ -v
"""

import os
import sys
from datetime import datetime, timezone

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import db as db_module  # noqa: E402


@pytest.fixture(autouse=True)
def _reset_connection_cache():
    """Tránh 1 test làm rò connection cache ảnh hưởng test khác."""
    db_module._connection = None
    yield
    db_module._connection = None


class FakeCursor:
    def __init__(self, rows):
        self.rows = rows
        self.executed = None

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return False

    def execute(self, query, values=None):
        self.executed = (query, values)

    def fetchall(self):
        return self.rows


class FakeConnection:
    def __init__(self, cursor):
        self._cursor = cursor
        self.closed = 0

    def cursor(self):
        return self._cursor


def test_get_recent_klines_reverses_desc_rows_to_ascending(monkeypatch):
    t2 = datetime(2026, 1, 3, tzinfo=timezone.utc)
    t1 = datetime(2026, 1, 2, tzinfo=timezone.utc)
    # DB trả về DESC (mới -> cũ) theo ORDER BY open_time DESC trong query.
    cursor = FakeCursor(rows=[(t2, 102, 103, 101, 102.5, 20.0), (t1, 101, 102, 100, 101.5, 10.0)])
    monkeypatch.setattr(db_module, "get_connection", lambda: FakeConnection(cursor))

    result = db_module.get_recent_klines("FPT", "1d", limit=2)

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
    cursor = FakeCursor(rows=[])
    monkeypatch.setattr(db_module, "get_connection", lambda: FakeConnection(cursor))

    result = db_module.get_recent_klines("FPT", "1d")

    assert result == []


def test_get_recent_klines_filters_by_symbol_interval_market_and_limit(monkeypatch):
    cursor = FakeCursor(rows=[])
    monkeypatch.setattr(db_module, "get_connection", lambda: FakeConnection(cursor))

    db_module.get_recent_klines("fpt", "1d", limit=500)

    _query, values = cursor.executed
    assert "market = %s" in _query
    assert "klines" in _query
    # symbol phải được upper-case, market luôn cố định "hose", limit truyền đúng.
    assert values == ("FPT", "1d", "hose", 500)


def test_get_recent_klines_uses_default_limit_when_not_specified(monkeypatch):
    cursor = FakeCursor(rows=[])
    monkeypatch.setattr(db_module, "get_connection", lambda: FakeConnection(cursor))

    db_module.get_recent_klines("FPT", "1d")

    _query, values = cursor.executed
    assert values[-1] == 2000


def test_get_recent_klines_casts_numeric_fields_to_float(monkeypatch):
    # Kiểm tra riêng phần chuyển đổi kiểu dữ liệu (Decimal từ Postgres ->
    # float) không phụ thuộc mock connection — dùng row giả kiểu int (vẫn
    # phải convert được sang float). Dùng monkeypatch (không gán/del thủ
    # công) để không làm rò state module sang các test khác.
    t1 = datetime(2026, 1, 1, tzinfo=timezone.utc)
    cursor = FakeCursor(rows=[(t1, 100, 101, 99, 100, 15)])
    monkeypatch.setattr(db_module, "get_connection", lambda: FakeConnection(cursor))

    result = db_module.get_recent_klines("FPT", "1d", limit=1)

    assert result[0]["open"] == 100.0
    assert isinstance(result[0]["open"], float)
    assert result[0]["volume"] == 15.0


def test_get_recent_klines_does_not_call_real_psycopg2_connect(monkeypatch):
    # Bảo đảm test không lỡ chạm network/DB thật: nếu get_connection() bị gọi
    # xuống psycopg2.connect thật (không mock), test này phải raise/fail rõ
    # ràng thay vì lặng lẽ connect ra ngoài.
    def _boom(*args, **kwargs):
        raise AssertionError("Không được gọi psycopg2.connect thật trong unit test")

    monkeypatch.setattr(db_module.psycopg2, "connect", _boom)
    monkeypatch.delenv("DATABASE_URL", raising=False)

    with pytest.raises(RuntimeError):
        db_module.get_recent_klines("FPT", "1d")
