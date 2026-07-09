"""
Unit tests cho evaluation/calibration.py (recalibrate confidence bang
direction accuracy thuc te gan day).

Chạy: cd apps/prediction-engine && pytest
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from evaluation.calibration import calibrate_confidence, recent_direction_accuracy  # noqa: E402


def make_result(direction_correct):
    return {"direction_correct": direction_correct, "accuracy_pct": 99.0, "error_pct": 1.0}


def test_recent_direction_accuracy_returns_none_for_empty_history():
    assert recent_direction_accuracy([]) is None


def test_recent_direction_accuracy_computes_ratio():
    history = [make_result(True), make_result(True), make_result(False), make_result(True)]

    result = recent_direction_accuracy(history, window=10)

    assert result == pytest.approx(0.75)


def test_recent_direction_accuracy_only_uses_window():
    # 10 ket qua False, sau do 4 ket qua True gan nhat -> window=4 phai chi
    # tinh tren 4 ket qua gan nhat (deu True), bo qua 10 ket qua cu.
    history = [make_result(False)] * 10 + [make_result(True)] * 4

    result = recent_direction_accuracy(history, window=4)

    assert result == pytest.approx(1.0)


def test_calibrate_confidence_returns_raw_when_not_enough_samples():
    history = [make_result(True)] * 5  # it hon min_samples mac dinh (20)

    result = calibrate_confidence(0.9, history, min_samples=20)

    assert result == 0.9


def test_calibrate_confidence_blends_towards_realized_rate_when_enough_samples():
    # Du doan luon SAI chieu trong qua khu gan day (realized_rate = 0.0),
    # nhung raw_confidence bao cao rat cao (0.95) -> sau calibrate phai giam
    # manh, phan anh dung thuc te la model dang du doan sai.
    history = [make_result(False)] * 30

    result = calibrate_confidence(0.95, history, min_samples=20, realized_weight=0.7)

    expected = 0.3 * 0.95 + 0.7 * 0.0
    assert result == pytest.approx(expected)
    assert result < 0.5


def test_calibrate_confidence_clamped_to_valid_range():
    history = [make_result(True)] * 30

    result = calibrate_confidence(1.5, history, min_samples=20, realized_weight=0.0)

    assert 0.0 <= result <= 1.0
