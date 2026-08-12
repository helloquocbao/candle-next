"""
Wrapper CHUNG cho dự đoán nhiều bước (multi-step forecast) bằng phương pháp
lặp (recursive): dự đoán bước t+1, COI NHƯ LÀ THẬT để nối vào history, rồi
dự đoán tiếp t+2 dựa trên history đã nối thêm đó, lặp lại đến khi đủ N bước.

Port nguyên vẹn từ prediction-engine (crypto, models/multi_step.py) — module
generic, không có gì đặc thù crypto/HOSE, chỉ khác nhau ở hàm dự đoán 1 bước
(predict_fn, ở đây là models/lightgbm_model.py::predict_next_candle cho
HOSE), logic lặp nhiều bước + giảm confidence dần theo khoảng cách dự đoán
là GIỐNG HỆT NHAU.

Đánh đổi của phương pháp lặp: sai số sẽ TÍCH LŨY qua từng bước vì phiên sau
dựa trên dự đoán (có thể sai) của phiên trước, KHÔNG PHẢI giá trị thực tế —
vì vậy confidence được nhân thêm `confidence_decay^step` để phản ánh đúng
mức độ không chắc chắn tăng dần theo khoảng cách dự đoán.
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
        predict_fn: hàm dự đoán 1 bước, nhận `history` (list[dict] nến đã
            đóng) trả về dict {predicted_open, predicted_high, predicted_low,
            predicted_close, confidence} — chính là interface của
            models.lightgbm_model.predict_next_candle().
        history: danh sách nến đã đóng thật, sắp xếp thời gian tăng dần.
        n_steps: số bước cần dự đoán.
        confidence_decay: hệ số nhân confidence mỗi bước, trong khoảng (0, 1].

    Returns:
        list[dict]: N phần tử cùng dạng với predict_fn(), theo thứ tự từ
        gần nhất (t+1) đến xa nhất (t+n_steps).

    Raises:
        ValueError: nếu n_steps < 1 (lỗi từ history rỗng được để predict_fn
        tự báo, không kiểm tra lại ở đây).
    """
    if n_steps < 1:
        raise ValueError("forecast_n_steps: n_steps phải >= 1.")

    # Nến tổng hợp (synthetic) không có volume THẬT (không có model dự đoán
    # volume tương lai) — giữ nguyên volume THẬT gần nhất làm giá trị thay
    # thế xuyên suốt các bước, cần thiết cho predict_fn nào dùng feature
    # volume (vd LightGBM với relative_volume, xem
    # features/feature_builder.py).
    last_known_volume = history[-1].get("volume") if history else None

    working_history = list(history)
    predictions = []

    for step in range(n_steps):
        prediction = predict_fn(working_history)
        prediction = dict(prediction)
        prediction["confidence"] = prediction["confidence"] * (confidence_decay**step)
        predictions.append(prediction)

        # Nối dự đoán vừa rồi vào history như 1 nến "đã đóng" để làm đầu vào
        # cho bước tiếp theo.
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
