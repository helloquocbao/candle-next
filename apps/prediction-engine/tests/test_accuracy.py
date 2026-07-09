"""
Unit tests cho evaluation/accuracy.py (tinh MAPE + direction accuracy).

Chạy: cd apps/prediction-engine && pytest
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
    # Gia thuc te tang (tu 100 -> 105), du doan cung tang (tu 100 -> 103)
    # => direction_correct phai True du sai so gia tri.
    actual = {"close": 105.0}
    predicted = {"predicted_close": 103.0}

    result = compute_accuracy(actual, predicted, previous_close=100.0)

    assert result["direction_correct"] is True


def test_compute_accuracy_direction_incorrect_using_previous_close():
    # Gia thuc te tang, du doan lai giam => direction_correct phai False.
    actual = {"close": 105.0}
    predicted = {"predicted_close": 95.0}

    result = compute_accuracy(actual, predicted, previous_close=100.0)

    assert result["direction_correct"] is False


def test_compute_accuracy_accuracy_pct_never_negative():
    # Sai so > 100% van phai clamp accuracy_pct ve 0, khong am.
    actual = {"close": 10.0}
    predicted = {"predicted_close": 1000.0}

    result = compute_accuracy(actual, predicted)

    assert result["accuracy_pct"] == 0.0


def test_compute_accuracy_flat_prediction_is_not_automatically_correct():
    # Regression: du doan "khong doi" (predicted_direction == 0) KHONG duoc
    # tu dong tinh la dung chieu khi gia thuc te thuc su di chuyen (len hoac
    # xuong). Cong thuc cu actual_direction * predicted_direction >= 0 coi
    # day la dung (0 * x >= 0 luon True) -> bug da fix.
    actual = {"close": 105.0}
    predicted = {"predicted_close": 100.0}  # du doan bang chinh previous_close

    result = compute_accuracy(actual, predicted, previous_close=100.0)

    assert result["direction_correct"] is False


def test_compute_accuracy_flat_prediction_correct_when_actual_also_flat():
    # Ca hai cung dung yen (== 0) -> van tinh la dung chieu.
    actual = {"close": 100.0}
    predicted = {"predicted_close": 100.0}

    result = compute_accuracy(actual, predicted, previous_close=100.0)

    assert result["direction_correct"] is True
