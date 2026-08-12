"""
Unit tests cho tích hợp ensemble AI (DeepSeek) trong main.py::process_symbol
(prediction-engine-hose).

Toàn bộ I/O ngoài (DB, VNDIRECT, DeepSeek) được monkeypatch — không cần
Postgres/network thật. Chạy: cd apps/prediction-engine-hose && pytest
"""

import os
import sys
from datetime import date, timedelta

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import main as main_module  # noqa: E402
from price_limit import funnel_bounds  # noqa: E402


def _fake_history(n=30, start=20.0, step=0.01):
    base_date = date(2026, 1, 1)
    hist = []
    price = start
    for i in range(n):
        hist.append(
            {
                "symbol": "FPT",
                "interval": "1d",
                "openTime": (base_date + timedelta(days=i)).isoformat(),
                "closeTime": (base_date + timedelta(days=i)).isoformat(),
                "open": price,
                "high": price * 1.01,
                "low": price * 0.99,
                "close": price,
                "volume": 1000.0,
            }
        )
        price *= 1 + step
    return hist


@pytest.fixture(autouse=True)
def _stub_io(monkeypatch):
    calls = {"prediction_inserts": [], "ai_signal_inserts": []}
    monkeypatch.setattr(main_module, "upsert_kline", lambda kline: None)
    monkeypatch.setattr(
        main_module,
        "insert_prediction",
        lambda row: calls["prediction_inserts"].append(row) or len(calls["prediction_inserts"]),
    )
    monkeypatch.setattr(
        main_module,
        "insert_ai_signal",
        lambda row: calls["ai_signal_inserts"].append(row) or 1,
    )
    return calls


def test_ai_disabled_by_default_leaves_predictions_unchanged(monkeypatch, _stub_io):
    """
    Mac dinh (ai_advisor.DEEPSEEK_ENABLED=False), get_ai_signal() VAN duoc
    goi (khong throttle rieng nhu prediction-engine crypto, xem ghi chu trong
    main.py) nhung tu tra ve None NGAY LAP TUC (khong goi network that, xem
    ai_advisor.py::get_ai_signal) -> predictions khong bi anh huong.
    """
    assert main_module.ai_advisor.DEEPSEEK_ENABLED is False
    monkeypatch.setattr(main_module, "fetch_daily_ohlcv", lambda *a, **k: _fake_history())

    main_module.process_symbol("FPT")

    assert _stub_io["ai_signal_inserts"] == []
    for row in _stub_io["prediction_inserts"]:
        assert "deepseek" not in row["model_version"]


def test_ai_enabled_blends_without_funnel_clamp(monkeypatch, _stub_io):
    monkeypatch.setattr(main_module.ai_advisor, "DEEPSEEK_ENABLED", True)
    monkeypatch.setattr(main_module, "fetch_daily_ohlcv", lambda *a, **k: _fake_history())

    # AI de xuat tang gia rat manh (vuot xa +-7% cua HOSE) — theo hanh vi moi
    # (khong con phe~u), gia blend PHAI duoc phep vuot bien +-7% cu.
    fake_signal = {"direction": "up", "predicted_change_pct": 20.0, "confidence": 0.95, "reasoning": "test"}
    monkeypatch.setattr(main_module.ai_advisor, "get_ai_signal", lambda *a, **k: fake_signal)

    main_module.process_symbol("FPT")

    inserts = _stub_io["prediction_inserts"]
    assert len(inserts) == main_module.N_STEPS

    first = inserts[0]
    assert first["model_version"].endswith("+deepseek")
    for row in inserts[1:]:
        assert "deepseek" not in row["model_version"]

    # Khong con kep vao phe~u step=1: gia blend duoc phep vuot bien +-7% cu.
    ref_close = _fake_history()[-1]["close"]
    _, old_ceiling = funnel_bounds(ref_close, step=1)
    assert first["predicted_close"] > old_ceiling

    assert len(_stub_io["ai_signal_inserts"]) == 1
    ai_row = _stub_io["ai_signal_inserts"][0]
    assert ai_row["direction"] == "up"
    assert ai_row["prediction_id"] == 1  # insert_prediction gia lap tra ve len(list) = 1 cho ban ghi dau tien


def test_ai_signal_none_falls_back_to_quant_only(monkeypatch, _stub_io):
    monkeypatch.setattr(main_module.ai_advisor, "DEEPSEEK_ENABLED", True)
    monkeypatch.setattr(main_module, "fetch_daily_ohlcv", lambda *a, **k: _fake_history())
    monkeypatch.setattr(main_module.ai_advisor, "get_ai_signal", lambda *a, **k: None)

    main_module.process_symbol("FPT")

    assert _stub_io["ai_signal_inserts"] == []
    for row in _stub_io["prediction_inserts"]:
        assert "deepseek" not in row["model_version"]
