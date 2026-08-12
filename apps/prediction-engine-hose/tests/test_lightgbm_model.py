"""
Unit test cho src/models/lightgbm_model.py — đặc biệt là đường fallback an
toàn (chưa có model file -> load_model() trả None, không crash) và định
dạng kết quả predict_next_candle()/predict_next_n_candles(). Train 1 booster
LightGBM thật nhưng NHỎ trên dữ liệu tổng hợp (synthetic), KHÔNG gọi network.

Chạy: cd apps/prediction-engine-hose && python3 -m pytest tests/ -v
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
    """Booster tối thiểu chỉ để test wiring — không quan tâm độ chính xác."""
    rng = np.random.default_rng(0)
    X = rng.normal(0, 1, (100, len(FEATURE_COLUMNS)))
    y = rng.normal(0, 0.01, 100)
    dataset = lgb.Dataset(X, label=y, feature_name=FEATURE_COLUMNS)
    return lgb.train({"objective": "regression", "verbose": -1}, dataset, num_boost_round=5)


def test_model_path_uses_symbol_and_interval():
    path = lightgbm_model.model_path("fpt", "1d")
    assert path.endswith(os.path.join("FPT_1d.txt"))


def test_load_model_returns_none_when_file_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(lightgbm_model, "MODELS_DIR", str(tmp_path))
    assert lightgbm_model.load_model("FPT", "1d") is None


def test_load_model_returns_none_when_file_corrupt(tmp_path, monkeypatch):
    monkeypatch.setattr(lightgbm_model, "MODELS_DIR", str(tmp_path))
    bad_path = lightgbm_model.model_path("FPT", "1d")
    with open(bad_path, "w") as f:
        f.write("không phải file model thật")

    assert lightgbm_model.load_model("FPT", "1d") is None


def test_load_model_round_trips_saved_booster(tmp_path, monkeypatch):
    monkeypatch.setattr(lightgbm_model, "MODELS_DIR", str(tmp_path))
    booster = _train_tiny_booster()
    booster.save_model(lightgbm_model.model_path("FPT", "1d"))

    loaded = lightgbm_model.load_model("FPT", "1d")

    assert loaded is not None
    assert isinstance(loaded, lgb.Booster)


def test_predict_next_candle_raises_when_not_enough_history():
    booster = _train_tiny_booster()
    klines = make_klines(MIN_HISTORY_FOR_FEATURES - 5)

    with pytest.raises(ValueError):
        lightgbm_model.predict_next_candle(klines, booster)


def test_predict_next_candle_returns_expected_shape():
    booster = _train_tiny_booster()
    klines = make_klines(200)

    result = lightgbm_model.predict_next_candle(klines, booster)

    assert set(result.keys()) == {
        "predicted_open",
        "predicted_high",
        "predicted_low",
        "predicted_close",
        "confidence",
    }
    assert result["predicted_high"] >= result["predicted_low"]
    assert result["predicted_open"] == klines[-1]["close"]
    assert result["confidence"] == pytest.approx(0.5)


def test_predict_next_n_candles_returns_n_steps_with_decaying_confidence():
    booster = _train_tiny_booster()
    klines = make_klines(200)

    results = lightgbm_model.predict_next_n_candles(klines, booster, n_steps=5, confidence_decay=0.8)

    assert len(results) == 5
    confidences = [r["confidence"] for r in results]
    for prev, curr in zip(confidences, confidences[1:]):
        assert curr <= prev + 1e-9

    # Nến thứ 2 phải có predicted_open == predicted_close của nến thứ 1 (đã
    # nối vào history như 1 nến "đã đóng" thật sự, xem models/multi_step.py).
    assert results[1]["predicted_open"] == results[0]["predicted_close"]


def test_predict_next_n_candles_uses_default_confidence_decay():
    booster = _train_tiny_booster()
    klines = make_klines(200)

    results = lightgbm_model.predict_next_n_candles(klines, booster, n_steps=3)

    assert len(results) == 3
