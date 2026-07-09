"""
Baseline prediction model — EMA (Exponential Moving Average) don gian.

Day la mo hinh "Giai doan 1" theo project_technical_spec.md muc 4.1:
    "Baseline: mo hinh thong ke (EMA/ARIMA) de co ket qua nhanh, lam nen
    tang so sanh."

Khong dung ML/Genetic Algorithm o day — chi la uoc luong thong ke tren
lich su gia close cua N nen gan nhat.
"""

from __future__ import annotations

import numpy as np

from models.multi_step import forecast_n_steps

# So nen gan nhat toi da duoc dung de tinh EMA / ATR.
DEFAULT_LOOKBACK = 50
# Span cho EMA (giong tinh chat "so ky voi trong so giam dan").
DEFAULT_EMA_SPAN = 10
MODEL_VERSION = "baseline-ema-v1"


def _ema(values: np.ndarray, span: int) -> np.ndarray:
    """
    Tinh Exponential Moving Average tren mang 1 chieu `values`.

    alpha = 2 / (span + 1), cong thuc chuan cua EMA.
    Tra ve mang cung kich thuoc, phan tu dau tien = values[0].
    """
    alpha = 2.0 / (span + 1.0)
    ema = np.empty_like(values, dtype=float)
    ema[0] = values[0]
    for i in range(1, len(values)):
        ema[i] = alpha * values[i] + (1.0 - alpha) * ema[i - 1]
    return ema


def simple_atr(history: list[dict], lookback: int) -> float:
    """
    Uoc luong bien do trung binh (Average True Range don gian hoa).

    True range o day duoc xap xi bang (high - low) cua tung nen (khong tinh
    gap so voi close truoc do de giu baseline don gian). Tra ve trung binh
    cong cua (high - low) tren `lookback` nen gan nhat.

    Public (khong con prefix "_"): dung chung boi ca baseline EMA lan
    models/lightgbm_model.py de uoc luong predicted_high/predicted_low
    (ca 2 model deu chua co "sub-model" rieng du doan high/low, chi du doan
    close/return — xem ghi chu trong models/lightgbm_model.py).
    """
    recent = history[-lookback:]
    ranges = [float(c["high"]) - float(c["low"]) for c in recent]
    if not ranges:
        return 0.0
    return float(np.mean(ranges))


def _stability_confidence(closes: np.ndarray) -> float:
    """
    Uoc tinh confidence (0..1) dua tren do on dinh cua bien dong gan day.

    Y tuong: neu do lech chuan tuong doi (coefficient of variation) cua
    % thay doi gia giua cac nen lien tiep thap => thi truong on dinh hon
    => confidence cao hon. Neu bien dong manh/that thuong => confidence thap.
    """
    if len(closes) < 3:
        return 0.5  # khong du du lieu de danh gia, tra ve gia tri trung tinh

    pct_changes = np.diff(closes) / closes[:-1]
    volatility = float(np.std(pct_changes))

    # Chuan hoa: volatility ~0 -> confidence ~1; volatility lon -> confidence -> 0.
    # He so 50 la ngưỡng kinh nghiem (empirical) cho MVP, co the tinh chinh sau.
    confidence = 1.0 / (1.0 + 50.0 * volatility)
    return float(np.clip(confidence, 0.0, 1.0))


def predict_next_candle(
    history: list[dict],
    ema_span: int = DEFAULT_EMA_SPAN,
    lookback: int = DEFAULT_LOOKBACK,
) -> dict:
    """
    Du doan nen tiep theo dua tren lich su cac nen da dong gan nhat.

    Args:
        history: danh sach dict nen da dong, sap xep theo thoi gian tang dan.
                 Moi phan tu can co it nhat cac key: open, high, low, close.
                 (co the co them symbol, interval, openTime, closeTime, ...)
        ema_span: span dung cho EMA (mac dinh 10).
        lookback: so nen gan nhat toi da su dung de tinh toan (mac dinh 50).

    Returns:
        dict: {
            "predicted_open": float,
            "predicted_high": float,
            "predicted_low": float,
            "predicted_close": float,
            "confidence": float,  # 0..1
        }

    Raises:
        ValueError: neu history rong.
    """
    if not history:
        raise ValueError("predict_next_candle: history khong duoc rong.")

    recent_history = history[-lookback:]
    closes = np.array([float(c["close"]) for c in recent_history], dtype=float)

    current_candle = recent_history[-1]
    current_close = float(current_candle["close"])

    # EMA cua gia close -> uoc luong xu huong gia dong cua nen ke tiep.
    ema_values = _ema(closes, span=min(ema_span, max(len(closes), 1)))
    predicted_close = float(ema_values[-1])

    # predicted_open = close cua nen hien tai (nen moi mo cua = gia dong cua
    # nen truoc do, dung quy uoc thi truong lien tuc).
    predicted_open = current_close

    # Bien do trung binh (ATR don gian) de uoc luong high/low quanh predicted_close.
    atr = simple_atr(recent_history, lookback=lookback)
    half_range = atr / 2.0

    predicted_high = max(predicted_open, predicted_close) + half_range
    predicted_low = min(predicted_open, predicted_close) - half_range

    confidence = _stability_confidence(closes)

    return {
        "predicted_open": predicted_open,
        "predicted_high": predicted_high,
        "predicted_low": predicted_low,
        "predicted_close": predicted_close,
        "confidence": confidence,
    }


# He so giam confidence moi buoc xa hon trong du doan nhieu nen (xem
# predict_next_n_candles). 0.85 nghia la moi nen xa hon mat ~15% confidence
# so voi nen truoc do — gia tri kinh nghiem (empirical), co the tinh chinh sau.
DEFAULT_HORIZON_CONFIDENCE_DECAY = 0.85


def predict_next_n_candles(
    history: list[dict],
    ema_span: int = DEFAULT_EMA_SPAN,
    lookback: int = DEFAULT_LOOKBACK,
    n_steps: int = 10,
    confidence_decay: float = DEFAULT_HORIZON_CONFIDENCE_DECAY,
) -> list[dict]:
    """
    Du doan N nen tiep theo bang phuong phap lap (recursive multi-step):
    du doan nen t+1, COI NHU LA THAT de noi vao cuoi history, roi du doan
    tiep t+2 dua tren history da noi them do, lap lai den khi du N nen.

    Day la ky thuat pho bien cho multi-step forecast khi chi co 1 model
    single-step (EMA baseline nay) — danh doi: sai so se TICH LUY qua tung
    buoc vi nen sau dua tren du doan (co the sai) cua nen truoc, KHONG PHAI
    gia tri thuc te. Vi vay confidence duoc nhan them `confidence_decay^step`
    de phan anh dung muc do khong chac chan tang dan theo khoang cach du doan
    (xem them: frontend lam nen mo dan theo tung buoc, xem chartRenderer.js).

    Args:
        history: danh sach nen da dong that, sap xep thoi gian tang dan.
        n_steps: so nen can du doan (mac dinh 10).
        confidence_decay: he so nhan confidence moi buoc, trong khoang (0, 1].

    Returns:
        list[dict]: N phan tu cung dang voi predict_next_candle(), theo thu
        tu tu gan nhat (t+1) den xa nhat (t+n_steps).

    Raises:
        ValueError: neu history rong hoac n_steps < 1.
    """
    # predict_next_candle() da tu validate history rong -> khong can lap lai o day.
    # Logic lap nhieu buoc dung chung voi models/lightgbm_model.py, xem
    # models/multi_step.py::forecast_n_steps.
    return forecast_n_steps(
        lambda h: predict_next_candle(h, ema_span=ema_span, lookback=lookback),
        history,
        n_steps=n_steps,
        confidence_decay=confidence_decay,
    )
