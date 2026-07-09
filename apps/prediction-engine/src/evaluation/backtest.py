"""
Walk-forward scoring — danh gia 1 bo tham so baseline (ema_span, lookback)
tren 1 doan lich su nen, tra ve 1 gia tri fitness scalar.

Duoc dung lam `fitness_fn` cho optimization/genetic.py (ca trong backtest
offline va trong vong lap self-learning online cua main.py) — tach thanh
module rieng de khong lap lai logic walk-forward o nhieu noi.
"""

from __future__ import annotations

from evaluation.accuracy import compute_accuracy
from models.baseline import predict_next_candle

DEFAULT_MAPE_WEIGHT = 1.0
DEFAULT_WARMUP = 30


def score_params(
    history: list[dict],
    params: dict,
    warmup: int = DEFAULT_WARMUP,
    mape_weight: float = DEFAULT_MAPE_WEIGHT,
) -> float:
    """
    Walk-forward: voi moi buoc t tu `warmup` den het `history`, dung
    history[:t] de du doan history[t] (bang params["ema_span"] /
    params["lookback"]), so sanh voi gia tri thuc te history[t].

    Fitness tong hop = direction_accuracy_pct - mape_weight * mape_mean.
    Direction accuracy quan trong hon gia tri tuyet doi (spec muc 4.3: "chi
    so quan trong hon gia tri tuyet doi voi trader"), nen duoc cong truc
    tiep; MAPE duoc tru di (voi trong so) de phat hien mo hinh sai lech gia
    qua nhieu du direction dung.

    Args:
        history: danh sach nen da dong, sap xep theo thoi gian tang dan.
        params: dict co key "ema_span" va "lookback".
        warmup: so nen dau tien bo qua (chua du du lieu de danh gia on dinh).
        mape_weight: trong so tru MAPE trong fitness tong hop.

    Returns:
        float: fitness (cang cao cang tot). `float("-inf")` neu khong du du
               lieu de danh gia (len(history) <= warmup).
    """
    if len(history) <= warmup:
        return float("-inf")

    error_pcts = []
    direction_hits = 0
    total = 0

    for t in range(warmup, len(history)):
        train_history = history[:t]
        actual = history[t]
        previous_close = history[t - 1]["close"]

        prediction = predict_next_candle(
            train_history,
            ema_span=params["ema_span"],
            lookback=params["lookback"],
        )
        result = compute_accuracy(actual, prediction, previous_close=previous_close)

        error_pcts.append(result["error_pct"])
        direction_hits += int(result["direction_correct"])
        total += 1

    if total == 0:
        return float("-inf")

    mape_mean = sum(error_pcts) / total
    direction_accuracy_pct = 100.0 * direction_hits / total

    return direction_accuracy_pct - mape_weight * mape_mean
