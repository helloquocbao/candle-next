"""
Wrapper cho model LightGBM dự đoán % thay đổi giá (return) của phiên kế
tiếp — cho HOSE (daily bar), port từ prediction-engine (crypto,
models/lightgbm_model.py).

Khác với forecast_zone.py::build_forecast_zone (luôn có sẵn, không cần train
trước, thuần drift EMA + ATR), model này CẦN được train offline trước (xem
training/train_lightgbm.py) và lưu thành file .txt (định dạng native của
LightGBM) trước khi main.py có thể nạp và sử dụng. Nếu chưa có file model
cho 1 mã, main.py tự động fallback về forecast_zone.py (heuristic) — không
bao giờ crash vì thiếu model.
"""

from __future__ import annotations

import logging
import os
from typing import Optional

import lightgbm as lgb

from features.feature_builder import FEATURE_COLUMNS, build_inference_features
from forecast_zone import DEFAULT_CONFIDENCE_DECAY, simple_atr
from models.multi_step import forecast_n_steps

logger = logging.getLogger(__name__)

MODEL_VERSION = "hose-lightgbm-v1"

# Thư mục lưu model đã train — TÁCH RIÊNG khỏi model crypto (MODELS_DIR mặc
# định của prediction-engine là /app/trained_models) để không đè lẫn khi 2
# service cùng mount volume trên cùng host; mount volume riêng trong
# docker-compose.yml (xem infra/docker/docker-compose.yml) để không mất khi
# rebuild image/đổi code.
MODELS_DIR = os.getenv("HOSE_MODELS_DIR", "/app/trained_models_hose")


def model_path(symbol: str, interval: str) -> str:
    return os.path.join(MODELS_DIR, f"{symbol.upper()}_{interval}.txt")


def load_model(symbol: str, interval: str) -> Optional[lgb.Booster]:
    """Nạp model đã train từ đĩa, hoặc None nếu chưa có (fallback forecast_zone)."""
    path = model_path(symbol, interval)
    if not os.path.exists(path):
        return None
    try:
        return lgb.Booster(model_file=path)
    except Exception:  # noqa: BLE001 - file hỏng/không tương thích -> fallback an toàn
        logger.exception("Lỗi khi nạp model LightGBM từ %s, sẽ dùng fallback forecast_zone.", path)
        return None


def predict_next_candle(history: list[dict], booster: lgb.Booster) -> dict:
    """
    Dự đoán phiên tiếp theo bằng LightGBM — CÙNG interface trả về như
    forecast_zone.py để main.py có thể dùng chung
    models/multi_step.py::forecast_n_steps.

    Raises:
        ValueError: nếu chưa đủ lịch sử để tính feature (xem
        features/feature_builder.py::MIN_HISTORY_FOR_FEATURES).
    """
    features = build_inference_features(history)
    if features is None:
        raise ValueError("predict_next_candle (lightgbm): chưa đủ lịch sử để tính feature.")

    predicted_return = float(booster.predict(features[FEATURE_COLUMNS].to_numpy())[0])
    current_close = float(history[-1]["close"])
    predicted_open = current_close
    predicted_close = current_close * (1.0 + predicted_return)

    # Chưa có model riêng dự đoán high/low — dùng ATR như forecast_zone.py
    # (xem forecast_zone.py::simple_atr). Hướng mở rộng sau: train thêm model
    # riêng dự đoán biên độ (high-low) thay vì dùng xấp xỉ tính.
    atr = simple_atr(history, lookback=14)
    half_range = atr / 2.0
    predicted_high = max(predicted_open, predicted_close) + half_range
    predicted_low = min(predicted_open, predicted_close) - half_range

    return {
        "predicted_open": predicted_open,
        "predicted_high": predicted_high,
        "predicted_low": predicted_low,
        "predicted_close": predicted_close,
        # Confidence khởi tạo trung tính — KHÔNG có calibration theo accuracy
        # thực tế gần đây như bên crypto (main.py HOSE hiện chưa có vòng lặp
        # self-learning/accuracy_log tương tự) — có thể bổ sung sau.
        "confidence": 0.5,
    }


def predict_next_n_candles(
    history: list[dict],
    booster: lgb.Booster,
    n_steps: int = 5,
    confidence_decay: float = DEFAULT_CONFIDENCE_DECAY,
) -> list[dict]:
    """
    Dự đoán N phiên tiếp theo bằng LightGBM (multi-step, phương pháp lặp) —
    xem models/multi_step.py::forecast_n_steps để biết chi tiết + đánh đổi
    của phương pháp này.
    """
    return forecast_n_steps(
        lambda h: predict_next_candle(h, booster),
        history,
        n_steps=n_steps,
        confidence_decay=confidence_decay,
    )
