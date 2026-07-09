"""
Unit test cho training/train_lightgbm.py::_evaluate_on_validation — dac biet
la viec map lai index tu val_frame (da qua dropna) ve dung vi tri trong
klines GOC de so sanh cong bang voi naive/baseline.

Chạy: cd apps/prediction-engine && pytest
"""

import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from features.feature_builder import build_training_frame  # noqa: E402
from training.train_lightgbm import (  # noqa: E402
    DIRECTION_REGRESSION_TOLERANCE_PP,
    _evaluate_on_validation,
    should_deploy,
)


def make_report(lgbm_mape, naive_mape, baseline_mape, lgbm_direction, baseline_direction):
    return {
        "lgbm": {"direction_pct": lgbm_direction, "mape": lgbm_mape},
        "naive": {"direction_pct": None, "mape": naive_mape},
        "baseline": {"direction_pct": baseline_direction, "mape": baseline_mape},
    }


def test_should_deploy_true_when_mape_better_and_direction_tied():
    """Truong hop thuc te da gap: MAPE thang ro, direction lech nho (nhieu
    thong ke) — van duoc chap nhan trien khai (xem
    DIRECTION_REGRESSION_TOLERANCE_PP va quyet dinh cua chu du an)."""
    report = make_report(lgbm_mape=0.044, naive_mape=0.044, baseline_mape=0.079, lgbm_direction=49.0, baseline_direction=49.3)

    deploy, regression_pp = should_deploy(report)

    assert deploy is True
    assert regression_pp == pytest.approx(0.3)


def test_should_deploy_false_when_mape_worse_than_baseline():
    report = make_report(lgbm_mape=0.10, naive_mape=0.044, baseline_mape=0.079, lgbm_direction=55.0, baseline_direction=49.3)

    deploy, _ = should_deploy(report)

    assert deploy is False


def test_should_deploy_false_when_direction_regresses_beyond_tolerance():
    report = make_report(
        lgbm_mape=0.04,
        naive_mape=0.044,
        baseline_mape=0.079,
        lgbm_direction=40.0,  # kem baseline rat nhieu, vuot nguong cho phep
        baseline_direction=49.3,
    )

    deploy, regression_pp = should_deploy(report)

    assert deploy is False
    assert regression_pp > DIRECTION_REGRESSION_TOLERANCE_PP


def test_should_deploy_false_when_mape_worse_than_naive():
    report = make_report(lgbm_mape=0.05, naive_mape=0.044, baseline_mape=0.079, lgbm_direction=55.0, baseline_direction=49.3)

    deploy, _ = should_deploy(report)

    assert deploy is False


def make_klines(n, seed=0):
    rng = np.random.default_rng(seed)
    closes = 100 + np.cumsum(rng.normal(0, 1, n))
    return [
        {
            "open": float(c - 0.1),
            "high": float(c + 1),
            "low": float(c - 1),
            "close": float(c),
            "volume": float(10 + i % 5),
        }
        for i, c in enumerate(closes)
    ]


def test_evaluate_matches_naive_when_predicted_return_is_zero():
    """Du doan return = 0 moi luc tuong duong CHINH XAC voi chien luoc naive
    (khong doi) — day la phep thu chinh xac cua viec can chinh index."""
    klines = make_klines(100)
    frame = build_training_frame(klines)
    val_frame = frame.iloc[-10:]
    predicted_returns = np.zeros(len(val_frame))

    report = _evaluate_on_validation(klines, val_frame, predicted_returns)

    assert report["n"] == 10
    assert report["lgbm"]["direction_pct"] == report["naive"]["direction_pct"]
    assert report["lgbm"]["mape"] == pytest.approx(report["naive"]["mape"])


def test_evaluate_perfect_prediction_gives_zero_error():
    """Du doan dung CHINH XAC return that -> MAPE = 0, direction accuracy = 100%."""
    klines = make_klines(100)
    frame = build_training_frame(klines)
    val_frame = frame.iloc[-10:]
    perfect_returns = val_frame["target_return"].to_numpy()

    report = _evaluate_on_validation(klines, val_frame, perfect_returns)

    assert report["lgbm"]["direction_pct"] == 100.0
    assert report["lgbm"]["mape"] == pytest.approx(0.0, abs=1e-9)


def test_evaluate_includes_baseline_stats_when_enough_history():
    klines = make_klines(100)
    frame = build_training_frame(klines)
    val_frame = frame.iloc[-10:]
    predicted_returns = np.zeros(len(val_frame))

    report = _evaluate_on_validation(klines, val_frame, predicted_returns)

    assert report["baseline"]["direction_pct"] is not None
    assert report["baseline"]["mape"] is not None
    assert 0.0 <= report["baseline"]["direction_pct"] <= 100.0
