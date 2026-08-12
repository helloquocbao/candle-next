"""
Tính toán các chỉ số đánh giá độ chính xác của dự đoán — port nguyên vẹn từ
prediction-engine (crypto, evaluation/accuracy.py), module thuần không phụ
thuộc gì đặc thù crypto/HOSE.

    - MAPE (Mean Absolute Percentage Error) cho giá close.
    - Direction Accuracy (dự đoán đúng chiều tăng/giảm).
"""

from __future__ import annotations


def compute_accuracy(
    actual: dict,
    predicted: dict,
    previous_close: float | None = None,
) -> dict:
    """
    Tính sai số và độ chính xác giữa phiên thực tế (actual) và phiên đã dự
    đoán (predicted) cho giá close.

    Args:
        actual: dict phiên thực tế đã đóng, cần có key "close" (và lý tưởng
                là "open" để suy ra chiều tăng/giảm thực tế nếu không có
                previous_close).
        predicted: dict dự đoán, cần có key "predicted_close" (và lý tưởng
                   là "predicted_open" để suy ra chiều dự đoán).
        previous_close: giá close của phiên trước đó (dùng để xác định chiều
                        tăng/giảm thực tế và dự đoán một cách nhất quán).
                        Nếu None, sẽ fallback dùng actual["open"] /
                        predicted["predicted_open"] làm tham chiếu.

    Returns:
        dict: {
            "error_pct": float,          # MAPE (%) trên giá close
            "accuracy_pct": float,       # 100 - error_pct (không âm)
            "direction_correct": bool,   # dự đoán đúng chiều tăng/giảm?
        }

    Raises:
        ValueError: nếu actual["close"] == 0 (không tính được MAPE) hoặc
                    thiếu key bắt buộc.
    """
    if "close" not in actual:
        raise ValueError("compute_accuracy: actual thiếu key 'close'.")
    if "predicted_close" not in predicted:
        raise ValueError("compute_accuracy: predicted thiếu key 'predicted_close'.")

    actual_close = float(actual["close"])
    predicted_close = float(predicted["predicted_close"])

    if actual_close == 0:
        raise ValueError("compute_accuracy: actual close bằng 0, không tính được MAPE.")

    # MAPE trên giá close: (|actual - predicted| / actual) * 100
    error_pct = abs(actual_close - predicted_close) / abs(actual_close) * 100.0
    accuracy_pct = max(0.0, 100.0 - error_pct)

    # Xác định điểm tham chiếu để so sánh chiều tăng/giảm (phiên trước đó).
    if previous_close is not None:
        reference_actual = float(previous_close)
        reference_predicted = float(previous_close)
    else:
        reference_actual = float(actual.get("open", actual_close))
        reference_predicted = float(predicted.get("predicted_open", predicted_close))

    actual_direction = actual_close - reference_actual
    predicted_direction = predicted_close - reference_predicted

    # So sánh theo DẤU (sign), không dùng tích actual*predicted >= 0: cách cũ
    # coi predicted_direction == 0 (dự đoán "không đổi") là luôn đúng chiều
    # với mọi actual_direction (vì 0 * x >= 0 luôn True), gây ảo tưởng 100%
    # direction accuracy cho chiến lược "không đổi". Đúng chiều chỉ khi cả
    # hai cùng tăng, cùng giảm, hoặc cả hai đứng yên (== 0).
    def _sign(x: float) -> int:
        if x > 0:
            return 1
        if x < 0:
            return -1
        return 0

    direction_correct = _sign(actual_direction) == _sign(predicted_direction)

    return {
        "error_pct": error_pct,
        "accuracy_pct": accuracy_pct,
        "direction_correct": bool(direction_correct),
    }
