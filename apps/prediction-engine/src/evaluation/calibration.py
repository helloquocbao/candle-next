"""
Calibration cho confidence score du doan, dua tren do chinh xac THUC TE gan
day (direction accuracy) thay vi chi dua vao volatility don thuan.

Van de da phat hien qua backtest thuc nghiem: confidence tinh boi
models/baseline.py (_stability_confidence) chi dua tren do bien dong gan
day cua gia, KHONG tuong quan voi kha nang du doan dung chieu thuc te (chia
bucket theo confidence tang dan cho thay direction accuracy dao dong ngau
nhien, khong tang dan tuong ung). Ham o day recalibrate confidence bang
cach tron voi ti le du doan dung chieu THUC TE trong qua khu gan day
(accuracy_history do main.py duy tri) — phan anh dung nghia "confidence =
xac suat du doan nay dung" hon la chi la 1 chi so volatility.
"""

from __future__ import annotations

from typing import Iterable, Optional

DEFAULT_WINDOW = 50
DEFAULT_MIN_SAMPLES = 20
# Thuc nghiem tren du lieu BTCUSDT thuc (xem README.md): quet realized_weight
# tu 0.0 den 1.0 cho thay Brier score cai thien don dieu theo weight, gan
# nhu bao hoa quanh 0.85-1.0 (0.2696 vs 0.2673 o weight=1.0). Chon 0.85 —
# gan sat muc bao hoa nhung van giu 1 phan nho tin hieu volatility goc,
# tranh phu thuoc 100% vao 1 chi so duy nhat.
DEFAULT_REALIZED_WEIGHT = 0.85


def recent_direction_accuracy(
    accuracy_history: Iterable[dict], window: int = DEFAULT_WINDOW
) -> Optional[float]:
    """
    Ti le du doan dung chieu (key "direction_correct") trong `window` ket
    qua gan nhat cua `accuracy_history`.

    Args:
        accuracy_history: danh sach/deque cac dict ket qua compute_accuracy(),
                           sap xep theo thoi gian tang dan (cu -> moi).
        window: so ket qua gan nhat toi da duoc xet.

    Returns:
        float | None: ti le (0..1), hoac None neu accuracy_history rong.
    """
    history = list(accuracy_history)
    if not history:
        return None

    recent = history[-window:]
    return sum(1 for r in recent if r["direction_correct"]) / len(recent)


def calibrate_confidence(
    raw_confidence: float,
    accuracy_history: Iterable[dict],
    window: int = DEFAULT_WINDOW,
    min_samples: int = DEFAULT_MIN_SAMPLES,
    realized_weight: float = DEFAULT_REALIZED_WEIGHT,
) -> float:
    """
    Tron `raw_confidence` (uoc luong tu volatility gia, xem
    models/baseline.py::_stability_confidence) voi ti le du doan dung chieu
    THUC TE gan day (`recent_direction_accuracy`), de confidence phan anh
    dung nang luc du doan thuc su cua model thay vi chi do "on dinh gia".

    Chi ap dung recalibration khi da co it nhat `min_samples` ket qua trong
    lich su — voi mau qua nho, ti le du doan dung chieu thuc te qua nhieu
    nhieu (noisy), recalibrate som se lam confidence kem tin cay hon, khong
    hon.

    Args:
        raw_confidence: confidence goc (0..1) tu predict_next_candle().
        accuracy_history: lich su ket qua compute_accuracy() gan day.
        window: so ket qua gan nhat dung de tinh realized rate.
        min_samples: so mau toi thieu truoc khi ap dung calibration.
        realized_weight: trong so cua ti le thuc te trong hon hop (0..1);
                         phan con lai (1 - realized_weight) la trong so cua
                         raw_confidence.

    Returns:
        float: confidence da calibrate, clamp trong [0, 1]. Tra ve nguyen
               `raw_confidence` neu chua du mau.
    """
    history = list(accuracy_history)
    if len(history) < min_samples:
        return raw_confidence

    realized_rate = recent_direction_accuracy(history, window=window)
    if realized_rate is None:
        return raw_confidence

    blended = (1.0 - realized_weight) * raw_confidence + realized_weight * realized_rate
    return max(0.0, min(1.0, blended))
