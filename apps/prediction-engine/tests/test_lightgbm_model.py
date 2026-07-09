"""
Unit test cho models/lightgbm_model.py — dac biet la duong fallback an toan
(chua co model -> None, khong crash) va dinh dang ket qua predict_next_candle
khop voi models/baseline.py (de main.py dung chung duoc).

Chạy: cd apps/prediction-engine && pytest
"""

import os
import sys

import lightgbm as lgb
import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from features.feature_builder import FEATURE_COLUMNS, MIN_HISTORY_FOR_FEATURES  # noqa: E402
from models import lightgbm_model  # noqa: E402


def make_klines(n, seed=0):
    rng = np.random.default_rng(seed)
    closes = 100 + np.cumsum(rng.normal(0, 1, n))
    return [
        {
            "open": float(c - 0.1),
            "high": float(c + 1),
            "low": float(c - 1),
            "close": float(c),
            "volume": float(10 + i % 5),
        }
        for i, c in enumerate(closes)
    ]


def _train_tiny_booster() -> lgb.Booster:
    """Booster toi thieu chi de test wiring — khong quan tam do chinh xac."""
    rng = np.random.default_rng(0)
    X = rng.normal(0, 1, (100, len(FEATURE_COLUMNS)))
    y = rng.normal(0, 0.01, 100)
    dataset = lgb.Dataset(X, label=y, feature_name=FEATURE_COLUMNS)
    return lgb.train({"objective": "regression", "verbose": -1}, dataset, num_boost_round=5)


def test_load_model_returns_none_when_file_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(lightgbm_model, "MODELS_DIR", str(tmp_path))
    assert lightgbm_model.load_model("BTCUSDT", "1m") is None


def test_load_model_returns_none_when_file_corrupt(tmp_path, monkeypatch):
    monkeypatch.setattr(lightgbm_model, "MODELS_DIR", str(tmp_path))
    bad_path = lightgbm_model.model_path("BTCUSDT", "1m")
    with open(bad_path, "w") as f:
        f.write("khong phai file model that")

    assert lightgbm_model.load_model("BTCUSDT", "1m") is None


def test_load_model_round_trips_saved_booster(tmp_path, monkeypatch):
    monkeypatch.setattr(lightgbm_model, "MODELS_DIR", str(tmp_path))
    booster = _train_tiny_booster()
    booster.save_model(lightgbm_model.model_path("BTCUSDT", "1m"))

    loaded = lightgbm_model.load_model("BTCUSDT", "1m")

    assert loaded is not None
    assert isinstance(loaded, lgb.Booster)


def test_predict_next_candle_raises_when_not_enough_history():
    booster = _train_tiny_booster()
    klines = make_klines(MIN_HISTORY_FOR_FEATURES - 5)

    with pytest.raises(ValueError):
        lightgbm_model.predict_next_candle(klines, booster)


def test_predict_next_candle_returns_same_shape_as_baseline():
    from models.baseline import predict_next_candle as baseline_predict

    booster = _train_tiny_booster()
    klines = make_klines(200)

    ml_result = lightgbm_model.predict_next_candle(klines, booster)
    baseline_result = baseline_predict(klines)

    assert set(ml_result.keys()) == set(baseline_result.keys())
    assert ml_result["predicted_high"] >= ml_result["predicted_low"]
    assert ml_result["predicted_open"] == klines[-1]["close"]


def test_predict_next_n_candles_returns_n_steps_with_decaying_confidence():
    booster = _train_tiny_booster()
    klines = make_klines(200)

    results = lightgbm_model.predict_next_n_candles(klines, booster, n_steps=5, confidence_decay=0.8)

    assert len(results) == 5
    confidences = [r["confidence"] for r in results]
    for prev, curr in zip(confidences, confidences[1:]):
        assert curr <= prev + 1e-9

    # Nen thu 2 phai co predicted_open == predicted_close cua nen thu 1 (da
    # noi vao history nhu 1 nen "da dong" that su, xem models/multi_step.py).
    assert results[1]["predicted_open"] == results[0]["predicted_close"]
