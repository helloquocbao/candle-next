"""
Tinh toan cac chi so danh gia do chinh xac cua du doan.

Theo project_technical_spec.md muc 4.3:
    - MAPE (Mean Absolute Percentage Error) cho gia close.
    - Direction Accuracy (du doan dung chieu tang/giam).
"""

from __future__ import annotations


def compute_accuracy(
    actual: dict,
    predicted: dict,
    previous_close: float | None = None,
) -> dict:
    """
    Tinh sai so va do chinh xac giua nen thuc te (actual) va nen da du doan
    (predicted) cho gia close.

    Args:
        actual: dict nen thuc te da dong, can co key "close" (va ly tuong
                la "open" de suy ra chieu tang/giam thuc te neu khong co
                previous_close).
        predicted: dict du doan, can co key "predicted_close" (va ly tuong
                   la "predicted_open" de suy ra chieu du doan).
        previous_close: gia close cua nen truoc do (dung de xac dinh chieu
                        tang/giam thuc te va du doan mot cach nhat quan).
                        Neu None, se fallback dung actual["open"] /
                        predicted["predicted_open"] lam tham chieu.

    Returns:
        dict: {
            "error_pct": float,          # MAPE (%) tren gia close
            "accuracy_pct": float,       # 100 - error_pct (khong am)
            "direction_correct": bool,   # du doan dung chieu tang/giam?
        }

    Raises:
        ValueError: neu actual["close"] == 0 (khong tinh duoc MAPE) hoac
                    thieu key bat buoc.
    """
    if "close" not in actual:
        raise ValueError("compute_accuracy: actual thieu key 'close'.")
    if "predicted_close" not in predicted:
        raise ValueError("compute_accuracy: predicted thieu key 'predicted_close'.")

    actual_close = float(actual["close"])
    predicted_close = float(predicted["predicted_close"])

    if actual_close == 0:
        raise ValueError("compute_accuracy: actual close bang 0, khong tinh duoc MAPE.")

    # MAPE tren gia close: (|actual - predicted| / actual) * 100
    error_pct = abs(actual_close - predicted_close) / abs(actual_close) * 100.0
    accuracy_pct = max(0.0, 100.0 - error_pct)

    # Xac dinh diem tham chieu de so sanh chieu tang/giam (nen truoc do).
    if previous_close is not None:
        reference_actual = float(previous_close)
        reference_predicted = float(previous_close)
    else:
        reference_actual = float(actual.get("open", actual_close))
        reference_predicted = float(predicted.get("predicted_open", predicted_close))

    actual_direction = actual_close - reference_actual
    predicted_direction = predicted_close - reference_predicted

    # So sanh theo DAU (sign), khong dung tich actual*predicted >= 0: cach cu
    # coi predicted_direction == 0 (du doan "khong doi") la luon dung chieu
    # voi moi actual_direction (vi 0 * x >= 0 luon True), gay ao tuong 100%
    # direction accuracy cho chien luoc "khong doi". Dung chieu chi khi ca
    # hai cung tang, cung giam, hoac ca hai dung yen (== 0).
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
