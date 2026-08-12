"""
Unit test cho src/models/multi_step.py — forecast_n_steps() (generic
recursive multi-step). Module không phụ thuộc lightgbm/vnstock, dùng
predict_fn giả (fake) để kiểm tra logic lặp thuần.

Chạy: cd apps/prediction-engine-hose && python3 -m pytest tests/ -v
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from models.multi_step import forecast_n_steps  # noqa: E402


def _fake_predict_fn(history: list[dict]) -> dict:
    """
    predict_fn giả: dự đoán phiên kế tiếp tăng đều +1 so với close gần nhất,
    confidence khởi tạo 1.0 (chưa decay) — dùng để kiểm tra hành vi lặp của
    forecast_n_steps mà không cần model thật.
    """
    last_close = float(history[-1]["close"])
    predicted_close = last_close + 1.0
    return {
        "predicted_open": last_close,
        "predicted_high": predicted_close + 0.5,
        "predicted_low": last_close - 0.5,
        "predicted_close": predicted_close,
        "confidence": 1.0,
    }


def _base_history():
    return [
        {"open": 98.0, "high": 101.0, "low": 97.0, "close": 100.0, "volume": 123.0},
    ]


def test_forecast_n_steps_returns_n_predictions():
    result = forecast_n_steps(_fake_predict_fn, _base_history(), n_steps=5, confidence_decay=0.9)
    assert len(result) == 5


def test_forecast_n_steps_raises_when_n_steps_invalid():
    with pytest.raises(ValueError):
        forecast_n_steps(_fake_predict_fn, _base_history(), n_steps=0, confidence_decay=0.9)


def test_forecast_n_steps_chains_predicted_close_into_next_open():
    # Bước 2 phải dùng close dự đoán của bước 1 làm nến "đã đóng" kế tiếp ->
    # predicted_open của bước 2 == predicted_close của bước 1.
    result = forecast_n_steps(_fake_predict_fn, _base_history(), n_steps=3, confidence_decay=1.0)
    assert result[1]["predicted_open"] == result[0]["predicted_close"]
    assert result[2]["predicted_open"] == result[1]["predicted_close"]


def test_forecast_n_steps_confidence_decays_per_step():
    result = forecast_n_steps(_fake_predict_fn, _base_history(), n_steps=4, confidence_decay=0.8)
    confidences = [r["confidence"] for r in result]
    for i, conf in enumerate(confidences):
        assert conf == pytest.approx(1.0 * (0.8**i))
    # Giảm dần (decay < 1) qua từng bước.
    for prev, curr in zip(confidences, confidences[1:]):
        assert curr < prev


def test_forecast_n_steps_confidence_constant_when_decay_is_1():
    result = forecast_n_steps(_fake_predict_fn, _base_history(), n_steps=3, confidence_decay=1.0)
    confidences = [r["confidence"] for r in result]
    assert all(c == pytest.approx(1.0) for c in confidences)


def test_forecast_n_steps_reuses_last_known_volume_for_synthetic_candles():
    # Volume THẬT gần nhất phải được giữ nguyên xuyên suốt các bước synthetic
    # (không có model dự đoán volume tương lai) — kiểm tra bằng predict_fn ghi
    # nhận volume của history truyền vào.
    seen_volumes = []

    def _predict_fn_records_volume(history: list[dict]) -> dict:
        seen_volumes.append(history[-1].get("volume"))
        last_close = float(history[-1]["close"])
        return {
            "predicted_open": last_close,
            "predicted_high": last_close + 1,
            "predicted_low": last_close - 1,
            "predicted_close": last_close + 1,
            "confidence": 1.0,
        }

    history = [{"open": 98.0, "high": 101.0, "low": 97.0, "close": 100.0, "volume": 555.0}]
    forecast_n_steps(_predict_fn_records_volume, history, n_steps=3, confidence_decay=0.9)

    # Bước 2 và 3 (dùng nến synthetic nối vào) vẫn phải thấy volume=555.0.
    assert seen_volumes[1] == 555.0
    assert seen_volumes[2] == 555.0


def test_forecast_n_steps_works_with_empty_last_known_volume():
    # History không có key "volume" -> synthetic candle không thêm volume,
    # không được raise lỗi.
    history = [{"open": 98.0, "high": 101.0, "low": 97.0, "close": 100.0}]
    result = forecast_n_steps(_fake_predict_fn, history, n_steps=2, confidence_decay=0.9)
    assert len(result) == 2
