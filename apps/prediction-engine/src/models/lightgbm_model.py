"""
Wrapper cho model LightGBM du doan % thay doi gia (return) cua nen ke tiep.

Khac voi models/baseline.py (luon co san, khong can train truoc), model nay
CAN duoc train offline truoc (xem training/train_lightgbm.py) va luu thanh
file .txt (dinh dang native cua LightGBM) truoc khi prediction-engine co the
nap va su dung. Neu chua co file model cho 1 cap symbol/interval, service se
tu dong fallback ve baseline EMA (xem main.py::PredictionEngine.__init__) —
khong bao gio crash vi thieu model.
"""

from __future__ import annotations

import logging
import os
from typing import Optional

import lightgbm as lgb

from features.feature_builder import FEATURE_COLUMNS, build_inference_features
from models.baseline import DEFAULT_HORIZON_CONFIDENCE_DECAY, simple_atr
from models.multi_step import forecast_n_steps

logger = logging.getLogger(__name__)

MODEL_VERSION = "lightgbm-v1"

# Thu muc luu model da train — nam NGOAI src/ (mount volume rieng trong
# docker-compose.yml, xem infra/docker/docker-compose.yml) de khong bi mat
# khi rebuild image / doi code (chi mat neu xoa volume tuong minh).
MODELS_DIR = os.getenv("MODELS_DIR", "/app/trained_models")


def model_path(symbol: str, interval: str) -> str:
    return os.path.join(MODELS_DIR, f"{symbol.upper()}_{interval}.txt")


def load_model(symbol: str, interval: str) -> Optional[lgb.Booster]:
    """Nap model da train tu dia, hoac None neu chua co (fallback ve baseline)."""
    path = model_path(symbol, interval)
    if not os.path.exists(path):
        return None
    try:
        return lgb.Booster(model_file=path)
    except Exception:  # noqa: BLE001 - file hong/khong tuong thich -> fallback an toan
        logger.exception("Loi khi nap model LightGBM tu %s, se dung fallback baseline.", path)
        return None


def predict_next_candle(history: list[dict], booster: lgb.Booster) -> dict:
    """
    Du doan nen tiep theo bang LightGBM — CUNG interface tra ve nhu
    models/baseline.py::predict_next_candle() de 2 model co the dung chung
    models/multi_step.py::forecast_n_steps() (xem main.py).

    Raises:
        ValueError: neu chua du lich su de tinh feature (xem
        features/feature_builder.py::MIN_HISTORY_FOR_FEATURES).
    """
    features = build_inference_features(history)
    if features is None:
        raise ValueError("predict_next_candle (lightgbm): chua du lich su de tinh feature.")

    predicted_return = float(booster.predict(features[FEATURE_COLUMNS].to_numpy())[0])
    current_close = float(history[-1]["close"])
    predicted_open = current_close
    predicted_close = current_close * (1.0 + predicted_return)

    # Chua co model rieng du doan high/low — dung ATR nhu baseline (xem
    # models/baseline.py::simple_atr). Huong mo rong sau: train them model
    # rieng du doan bien do (high-low) thay vi dung xap xi tinh.
    atr = simple_atr(history, lookback=14)
    half_range = atr / 2.0
    predicted_high = max(predicted_open, predicted_close) + half_range
    predicted_low = min(predicted_open, predicted_close) - half_range

    return {
        "predicted_open": predicted_open,
        "predicted_high": predicted_high,
        "predicted_low": predicted_low,
        "predicted_close": predicted_close,
        # Confidence khoi tao trung tinh — se duoc calibrate_confidence()
        # trong main.py dieu chinh theo do chinh xac THUC TE gan day, giong
        # het co che cua baseline (xem main.py::_make_new_prediction).
        "confidence": 0.5,
    }


def predict_next_n_candles(
    history: list[dict],
    booster: lgb.Booster,
    n_steps: int = 10,
    confidence_decay: float = DEFAULT_HORIZON_CONFIDENCE_DECAY,
) -> list[dict]:
    """
    Du doan N nen tiep theo bang LightGBM (multi-step, phuong phap lap) —
    xem models/multi_step.py::forecast_n_steps de biet chi tiet + danh doi
    cua phuong phap nay.
    """
    return forecast_n_steps(
        lambda h: predict_next_candle(h, booster),
        history,
        n_steps=n_steps,
        confidence_decay=confidence_decay,
    )
