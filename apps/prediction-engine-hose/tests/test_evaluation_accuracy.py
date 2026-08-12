"""
Unit test cho src/evaluation/accuracy.py — compute_accuracy() (tính MAPE +
direction accuracy). Module port nguyên vẹn từ prediction-engine (crypto),
tham khảo style từ apps/prediction-engine/tests/test_accuracy.py nhưng viết
lại đúng import path của bản HOSE (src/evaluation/accuracy.py).

Chạy: cd apps/prediction-engine-hose && python3 -m pytest tests/ -v
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from evaluation.accuracy import compute_accuracy  # noqa: E402


def test_compute_accuracy_perfect_prediction():
    actual = {"close": 100.0, "open": 98.0}
    predicted = {"predicted_close": 100.0, "predicted_open": 98.0}

    result = compute_accuracy(actual, predicted)

    assert result["error_pct"] == 0.0
    assert result["accuracy_pct"] == 100.0
    assert result["direction_correct"] is True


def test_compute_accuracy_computes_mape():
    actual = {"close": 100.0}
    predicted = {"predicted_close": 110.0}

    result = compute_accuracy(actual, predicted)

    assert result["error_pct"] == pytest.approx(10.0)
    assert result["accuracy_pct"] == pytest.approx(90.0)


def test_compute_accuracy_raises_when_actual_close_missing():
    with pytest.raises(ValueError):
        compute_accuracy({}, {"predicted_close": 100.0})


def test_compute_accuracy_raises_when_predicted_close_missing():
    with pytest.raises(ValueError):
        compute_accuracy({"close": 100.0}, {})


def test_compute_accuracy_raises_when_actual_close_zero():
    with pytest.raises(ValueError):
        compute_accuracy({"close": 0.0}, {"predicted_close": 1.0})


def test_compute_accuracy_direction_correct_using_previous_close():
    # Giá thực tế tăng (100 -> 105), dự đoán cũng tăng (100 -> 103) => đúng
    # chiều dù sai số giá trị.
    actual = {"close": 105.0}
    predicted = {"predicted_close": 103.0}

    result = compute_accuracy(actual, predicted, previous_close=100.0)

    assert result["direction_correct"] is True


def test_compute_accuracy_direction_incorrect_using_previous_close():
    # Giá thực tế tăng, dự đoán lại giảm => sai chiều.
    actual = {"close": 105.0}
    predicted = {"predicted_close": 95.0}

    result = compute_accuracy(actual, predicted, previous_close=100.0)

    assert result["direction_correct"] is False


def test_compute_accuracy_accuracy_pct_never_negative():
    # Sai số > 100% vẫn phải clamp accuracy_pct về 0, không âm.
    actual = {"close": 10.0}
    predicted = {"predicted_close": 1000.0}

    result = compute_accuracy(actual, predicted)

    assert result["accuracy_pct"] == 0.0


def test_compute_accuracy_flat_prediction_is_not_automatically_correct():
    # Regression: dự đoán "không đổi" (predicted_direction == 0) KHÔNG được
    # tự động tính là đúng chiều khi giá thực tế thực sự di chuyển.
    actual = {"close": 105.0}
    predicted = {"predicted_close": 100.0}  # dự đoán bằng chính previous_close

    result = compute_accuracy(actual, predicted, previous_close=100.0)

    assert result["direction_correct"] is False


def test_compute_accuracy_flat_prediction_correct_when_actual_also_flat():
    # Cả hai cùng đứng yên (== 0) -> vẫn tính là đúng chiều.
    actual = {"close": 100.0}
    predicted = {"predicted_close": 100.0}

    result = compute_accuracy(actual, predicted, previous_close=100.0)

    assert result["direction_correct"] is True


def test_compute_accuracy_falls_back_to_open_when_no_previous_close():
    # Không truyền previous_close -> dùng actual["open"]/predicted["predicted_open"]
    # làm điểm tham chiếu.
    actual = {"close": 105.0, "open": 100.0}
    predicted = {"predicted_close": 103.0, "predicted_open": 100.0}

    result = compute_accuracy(actual, predicted)

    assert result["direction_correct"] is True
