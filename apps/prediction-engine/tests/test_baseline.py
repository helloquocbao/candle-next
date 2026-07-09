"""
Unit tests cho models/baseline.py (EMA baseline model).

Chạy: cd apps/prediction-engine && pytest
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from models.baseline import predict_next_candle, predict_next_n_candles  # noqa: E402


def make_candle(open_, high, low, close):
    return {"open": open_, "high": high, "low": low, "close": close}


def test_predict_next_candle_raises_on_empty_history():
    with pytest.raises(ValueError):
        predict_next_candle([])


def test_predict_next_candle_returns_expected_keys():
    history = [make_candle(100, 105, 95, 100 + i) for i in range(10)]
    result = predict_next_candle(history)

    assert set(result.keys()) == {
        "predicted_open",
        "predicted_high",
        "predicted_low",
        "predicted_close",
        "confidence",
    }


def test_predict_next_candle_open_equals_last_close():
    history = [make_candle(100, 105, 95, 100), make_candle(100, 106, 96, 103)]
    result = predict_next_candle(history)

    assert result["predicted_open"] == history[-1]["close"]


def test_predict_next_candle_high_gte_low():
    history = [make_candle(100, 105, 95, 100 + i) for i in range(20)]
    result = predict_next_candle(history)

    assert result["predicted_high"] >= result["predicted_low"]


def test_predict_next_candle_confidence_in_range():
    history = [make_candle(100, 105, 95, 100 + (i % 3)) for i in range(30)]
    result = predict_next_candle(history)

    assert 0.0 <= result["confidence"] <= 1.0


def test_predict_next_candle_single_candle_history():
    # history chi co 1 nen van phai chay duoc, khong raise.
    history = [make_candle(100, 102, 98, 101)]
    result = predict_next_candle(history)

    assert result["predicted_close"] == 101
    assert result["predicted_open"] == 101


def test_predict_next_n_candles_raises_on_invalid_n_steps():
    history = [make_candle(100, 105, 95, 100 + i) for i in range(10)]
    with pytest.raises(ValueError):
        predict_next_n_candles(history, n_steps=0)


def test_predict_next_n_candles_returns_n_predictions():
    history = [make_candle(100, 105, 95, 100 + i) for i in range(20)]
    results = predict_next_n_candles(history, n_steps=10)

    assert len(results) == 10
    for result in results:
        assert set(result.keys()) == {
            "predicted_open",
            "predicted_high",
            "predicted_low",
            "predicted_close",
            "confidence",
        }


def test_predict_next_n_candles_chains_open_to_previous_close():
    """Nen thu i+1 phai co predicted_open == predicted_close cua nen thu i
    (vi da noi du doan truoc vao history nhu 1 nen "da dong" that su)."""
    history = [make_candle(100, 105, 95, 100 + i) for i in range(20)]
    results = predict_next_n_candles(history, n_steps=5)

    for prev, curr in zip(results, results[1:]):
        assert curr["predicted_open"] == prev["predicted_close"]


def test_predict_next_n_candles_confidence_decays_each_step():
    history = [make_candle(100, 105, 95, 100 + (i % 3)) for i in range(30)]
    results = predict_next_n_candles(history, n_steps=5, confidence_decay=0.85)

    confidences = [r["confidence"] for r in results]
    # Moi buoc phai <= buoc truoc (decay < 1) — cang xa cang it chac chan.
    for prev, curr in zip(confidences, confidences[1:]):
        assert curr <= prev + 1e-9


def test_predict_next_n_candles_matches_single_step_on_first_prediction():
    """Nen dau tien (t+1) cua predict_next_n_candles phai giong het ket qua
    cua predict_next_candle() tren cung history — chi khac tu buoc 2 tro di."""
    history = [make_candle(100, 105, 95, 100 + i) for i in range(15)]
    single = predict_next_candle(history)
    multi = predict_next_n_candles(history, n_steps=3)

    assert multi[0]["predicted_open"] == single["predicted_open"]
    assert multi[0]["predicted_close"] == single["predicted_close"]
    assert multi[0]["confidence"] == single["confidence"]
