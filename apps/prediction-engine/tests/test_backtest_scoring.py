"""
Unit tests cho evaluation/backtest.py (score_params — walk-forward scoring).

Chạy: cd apps/prediction-engine && pytest
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from evaluation.backtest import score_params  # noqa: E402


def make_candle(close):
    return {"open": close, "high": close + 1, "low": close - 1, "close": close}


def test_score_params_returns_neg_inf_when_not_enough_history():
    history = [make_candle(100 + i) for i in range(5)]

    score = score_params(history, {"ema_span": 10, "lookback": 50}, warmup=30)

    assert score == float("-inf")


def test_score_params_returns_finite_float_with_enough_history():
    history = [make_candle(100 + (i % 5)) for i in range(80)]

    score = score_params(history, {"ema_span": 10, "lookback": 50}, warmup=30)

    assert score != float("-inf")
    assert isinstance(score, float)


def test_score_params_flat_price_history_scores_near_perfect():
    # Gia khong doi tuyet doi qua toan bo lich su -> EMA du doan dung chinh
    # xac (error=0%) va huong "dung yen" cung khop voi thuc te (dung chieu)
    # o moi buoc -> fitness phai bang dung 100 (direction_accuracy=100,
    # mape_mean=0).
    history = [make_candle(100) for _ in range(80)]

    score = score_params(history, {"ema_span": 5, "lookback": 50}, warmup=30)

    assert score == pytest.approx(100.0)


def test_score_params_is_deterministic():
    history = [make_candle(100 + (i % 7)) for i in range(80)]
    params = {"ema_span": 8, "lookback": 40}

    first = score_params(history, params, warmup=30)
    second = score_params(history, params, warmup=30)

    assert first == second
