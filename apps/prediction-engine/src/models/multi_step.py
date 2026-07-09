"""
Wrapper CHUNG cho du doan nhieu buoc (multi-step forecast) bang phuong phap
lap (recursive): du doan buoc t+1, COI NHU LA THAT de noi vao history, roi
du doan tiep t+2 dua tren history da noi them do, lap lai den khi du N buoc.

Dung chung boi CA baseline EMA (models/baseline.py) LAN LightGBM
(models/lightgbm_model.py) — 2 model chi khac nhau o ham du doan 1 buoc
(predict_fn), logic lap nhieu buoc + giam confidence dan theo khoang cach
du doan la GIONG HET NHAU, tach ra day de khong lap lai code.

Danh doi cua phuong phap lap: sai so se TICH LUY qua tung buoc vi nen sau
dua tren du doan (co the sai) cua nen truoc, KHONG PHAI gia tri thuc te —
vi vay confidence duoc nhan them `confidence_decay^step` de phan anh dung
muc do khong chac chan tang dan theo khoang cach du doan.
"""

from __future__ import annotations

from typing import Callable

SingleStepPredictFn = Callable[[list[dict]], dict]


def forecast_n_steps(
    predict_fn: SingleStepPredictFn,
    history: list[dict],
    n_steps: int,
    confidence_decay: float,
) -> list[dict]:
    """
    Args:
        predict_fn: ham du doan 1 buoc, nhan `history` (list[dict] nen da
            dong) tra ve dict {predicted_open, predicted_high, predicted_low,
            predicted_close, confidence} — chinh la interface cua
            models.baseline.predict_next_candle() va
            models.lightgbm_model.predict_next_candle().
        history: danh sach nen da dong that, sap xep thoi gian tang dan.
        n_steps: so buoc can du doan.
        confidence_decay: he so nhan confidence moi buoc, trong khoang (0, 1].

    Returns:
        list[dict]: N phan tu cung dang voi predict_fn(), theo thu tu tu
        gan nhat (t+1) den xa nhat (t+n_steps).

    Raises:
        ValueError: neu n_steps < 1 (loi tu history rong duoc de predict_fn
        tu bao, khong kiem tra lai o day).
    """
    if n_steps < 1:
        raise ValueError("forecast_n_steps: n_steps phai >= 1.")

    # Nen tong hop (synthetic) khong co volume THAT (khong co model du doan
    # volume tuong lai) — giu nguyen volume THAT gan nhat lam gia tri thay
    # the xuyen suot cac buoc, can thiet cho predict_fn nao dung feature
    # volume (vd LightGBM voi relative_volume, xem
    # features/feature_builder.py) — predict_fn khong dung volume (vd
    # baseline EMA) don gian se bo qua field nay.
    last_known_volume = history[-1].get("volume") if history else None

    working_history = list(history)
    predictions = []

    for step in range(n_steps):
        prediction = predict_fn(working_history)
        prediction = dict(prediction)
        prediction["confidence"] = prediction["confidence"] * (confidence_decay**step)
        predictions.append(prediction)

        # Noi du doan vua roi vao history nhu 1 nen "da dong" de lam dau vao
        # cho buoc tiep theo.
        synthetic_candle = {
            "open": prediction["predicted_open"],
            "high": prediction["predicted_high"],
            "low": prediction["predicted_low"],
            "close": prediction["predicted_close"],
        }
        if last_known_volume is not None:
            synthetic_candle["volume"] = last_known_volume
        working_history.append(synthetic_candle)

    return predictions
