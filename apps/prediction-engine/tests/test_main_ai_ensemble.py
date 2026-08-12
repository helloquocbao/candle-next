"""
Unit tests cho tich hop ensemble AI (DeepSeek) trong main.py::PredictionEngine.

Khong goi network that: ai_advisor.get_ai_signal duoc monkeypatch truc tiep
tren main_module.ai_advisor (module object), giu nguyen huong dan
"Tat ca I/O ben ngoai duoc monkeypatch" cua test_main_self_learning.py.

Chay: cd apps/prediction-engine && pytest
"""

import json
import os
import sys
from datetime import datetime, timedelta

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import main as main_module  # noqa: E402
from main import PredictionEngine  # noqa: E402


@pytest.fixture(autouse=True)
def _stub_io(monkeypatch):
    calls = {
        "prediction_inserts": [],
        "prediction_publishes": [],
        "ai_signal_inserts": [],
    }
    monkeypatch.setattr(main_module, "insert_accuracy", lambda row: 1)
    monkeypatch.setattr(
        main_module,
        "insert_prediction",
        lambda row: calls["prediction_inserts"].append(row) or len(calls["prediction_inserts"]),
    )
    monkeypatch.setattr(main_module, "publish_accuracy", lambda *a, **k: None)
    monkeypatch.setattr(
        main_module,
        "publish_prediction",
        lambda symbol, interval, data: calls["prediction_publishes"].append(data),
    )
    monkeypatch.setattr(main_module, "insert_model_params_history", lambda row: None)
    monkeypatch.setattr(
        main_module,
        "insert_ai_signal",
        lambda row: calls["ai_signal_inserts"].append(row) or 1,
    )
    return calls


def make_kline(open_time_iso, close, is_closed=True):
    return {
        "openTime": open_time_iso,
        "open": close,
        "high": close + 1,
        "low": close - 1,
        "close": close,
        "isClosed": is_closed,
    }


def feed_candles(engine: PredictionEngine, closes: list[float]) -> None:
    base = datetime(2026, 1, 1)
    for i, close in enumerate(closes):
        open_time = (base + timedelta(minutes=i)).isoformat()
        kline = make_kline(open_time, close)
        payload = json.dumps({"type": "kline", "data": kline})
        engine.handle_message(payload)


def test_ai_disabled_by_default_leaves_predictions_unchanged(monkeypatch, _stub_io):
    """Mac dinh (ai_advisor.DEEPSEEK_ENABLED=False), khong duoc goi get_ai_signal
    va khong co model_version nao bi gan them hau to '+deepseek'."""
    assert main_module.ai_advisor.DEEPSEEK_ENABLED is False

    def _fail_if_called(*a, **k):
        raise AssertionError("get_ai_signal khong duoc goi khi DEEPSEEK_ENABLED=False")

    monkeypatch.setattr(main_module.ai_advisor, "get_ai_signal", _fail_if_called)

    engine = PredictionEngine(symbol="BTCUSDT", interval="1m")
    feed_candles(engine, [100, 101, 102])

    assert _stub_io["ai_signal_inserts"] == []
    for row in _stub_io["prediction_inserts"]:
        assert "deepseek" not in row["model_version"]


def test_ai_enabled_blends_first_step_only(monkeypatch, _stub_io):
    monkeypatch.setattr(main_module.ai_advisor, "DEEPSEEK_ENABLED", True)
    monkeypatch.setattr(main_module, "AI_REFRESH_EVERY_N_CANDLES", 1)

    fake_signal = {
        "direction": "up",
        "predicted_change_pct": 5.0,
        "confidence": 0.9,
        "reasoning": "test",
    }
    monkeypatch.setattr(main_module.ai_advisor, "get_ai_signal", lambda *a, **k: fake_signal)

    engine = PredictionEngine(symbol="BTCUSDT", interval="1m")
    feed_candles(engine, [100])  # 1 nen dong -> 1 chu ky _make_new_prediction

    inserts = _stub_io["prediction_inserts"]
    assert len(inserts) == main_module.PREDICTION_HORIZON

    # Chi buoc dau tien (t+1) duoc gan tag "+deepseek" va ghi audit AI.
    assert inserts[0]["model_version"].endswith("+deepseek")
    for row in inserts[1:]:
        assert "deepseek" not in row["model_version"]

    assert len(_stub_io["ai_signal_inserts"]) == 1
    ai_row = _stub_io["ai_signal_inserts"][0]
    assert ai_row["direction"] == "up"
    assert ai_row["predicted_change_pct"] == 5.0
    assert ai_row["prediction_id"] == inserts[0]["id"]


def test_ai_signal_none_falls_back_to_quant_only(monkeypatch, _stub_io):
    """Neu get_ai_signal tra ve None (loi mang/timeout/parse that bai), luong
    du doan phai giong het nhu khi AI bi tat hoan toan — khong bao gio crash."""
    monkeypatch.setattr(main_module.ai_advisor, "DEEPSEEK_ENABLED", True)
    monkeypatch.setattr(main_module, "AI_REFRESH_EVERY_N_CANDLES", 1)
    monkeypatch.setattr(main_module.ai_advisor, "get_ai_signal", lambda *a, **k: None)

    engine = PredictionEngine(symbol="BTCUSDT", interval="1m")
    feed_candles(engine, [100])

    assert _stub_io["ai_signal_inserts"] == []
    for row in _stub_io["prediction_inserts"]:
        assert "deepseek" not in row["model_version"]


def test_ai_call_is_throttled_by_ai_refresh_every_n_candles(monkeypatch, _stub_io):
    monkeypatch.setattr(main_module.ai_advisor, "DEEPSEEK_ENABLED", True)
    monkeypatch.setattr(main_module, "AI_REFRESH_EVERY_N_CANDLES", 3)

    call_count = {"n": 0}

    def _counting_signal(*a, **k):
        call_count["n"] += 1
        return {"direction": "up", "predicted_change_pct": 1.0, "confidence": 0.5, "reasoning": ""}

    monkeypatch.setattr(main_module.ai_advisor, "get_ai_signal", _counting_signal)

    engine = PredictionEngine(symbol="BTCUSDT", interval="1m")
    # candles_since_ai_call bat dau = AI_REFRESH_EVERY_N_CANDLES -> nen dau
    # tien (feed candle dau) da du dieu kien goi ngay (xem __init__).
    feed_candles(engine, [100, 101, 102, 103, 104, 105])

    # 6 nen dong -> 6 lan _make_new_prediction; goi AI o chu ky 1, 4 (moi 3 lan).
    assert call_count["n"] == 2
