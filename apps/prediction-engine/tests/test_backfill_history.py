"""
Unit test cho training/backfill_history.py — dac biet la logic phan trang
(paginate forward tu qua khu den hien tai, dung lai dung luc) va khong goi
Binance/DB that.

Chạy: cd apps/prediction-engine && pytest
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from training import backfill_history  # noqa: E402


def make_row(open_time_ms, close=100.0):
    # [openTime, open, high, low, close, volume, closeTime, ...]
    return [open_time_ms, close, close + 1, close - 1, close, 10.0, open_time_ms + 59_999]


def test_backfill_stops_when_page_shorter_than_max(monkeypatch):
    """Trang cuoi cung (it hon MAX_CANDLES_PER_REQUEST) bao hieu da het du lieu."""
    written = []
    monkeypatch.setattr(backfill_history, "upsert_kline", lambda **kwargs: written.append(kwargs))

    rows = [make_row(1_700_000_000_000 + i * 60_000) for i in range(3)]
    monkeypatch.setattr(backfill_history, "_fetch_klines_page", lambda *a, **k: rows)

    total = backfill_history.backfill_symbol_interval("BTCUSDT", "1m", target_candles=100)

    assert total == 3
    assert len(written) == 3
    assert written[0]["symbol"] == "BTCUSDT"
    assert written[0]["interval"] == "1m"


def test_backfill_stops_when_empty_page_returned(monkeypatch):
    written = []
    monkeypatch.setattr(backfill_history, "upsert_kline", lambda **kwargs: written.append(kwargs))
    monkeypatch.setattr(backfill_history, "_fetch_klines_page", lambda *a, **k: [])

    total = backfill_history.backfill_symbol_interval("BTCUSDT", "1m", target_candles=100)

    assert total == 0
    assert written == []


def test_backfill_paginates_multiple_full_pages(monkeypatch):
    """Trang DAY DU (== MAX_CANDLES_PER_REQUEST) phai goi tiep trang ke tiep,
    voi startTime = open_time cuoi cung + do dai 1 nen."""
    written = []
    monkeypatch.setattr(backfill_history, "upsert_kline", lambda **kwargs: written.append(kwargs))
    monkeypatch.setattr(backfill_history, "MAX_CANDLES_PER_REQUEST", 2)
    monkeypatch.setattr(backfill_history, "REQUEST_DELAY_SECONDS", 0)

    call_log = []

    def fake_fetch(symbol, interval, start_time_ms, limit=2):
        call_log.append(start_time_ms)
        if len(call_log) == 1:
            return [make_row(start_time_ms), make_row(start_time_ms + 60_000)]
        # Trang thu 2: it hon MAX_CANDLES_PER_REQUEST -> dung lai.
        return [make_row(start_time_ms)]

    monkeypatch.setattr(backfill_history, "_fetch_klines_page", fake_fetch)

    total = backfill_history.backfill_symbol_interval("BTCUSDT", "1m", target_candles=10)

    assert total == 3
    assert len(call_log) == 2
    # Trang 2 phai bat dau ngay sau nen cuoi cung cua trang 1.
    assert call_log[1] == call_log[0] + 2 * 60_000


def test_backfill_raises_on_unknown_interval():
    with pytest.raises(ValueError):
        backfill_history.backfill_symbol_interval("BTCUSDT", "not-a-real-interval")
