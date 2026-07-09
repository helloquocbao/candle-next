"""
Unit test cho features/technical_indicators.py — kiem tra cong thuc dung
huong (khong can dung tuyet doi tung con so, chi can dung TINH CHAT toan hoc
co ban cua tung chi bao).

Chạy: cd apps/prediction-engine && pytest
"""

import os
import sys

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from features.technical_indicators import (  # noqa: E402
    bollinger_bands,
    macd,
    relative_volume,
    rolling_volatility,
    rsi,
)


def test_rsi_is_100_when_price_only_increases():
    close = pd.Series(np.arange(1, 50, dtype=float))  # tang deu, khong bao gio giam
    result = rsi(close, period=14)
    assert result.dropna().eq(100.0).all()


def test_rsi_is_bounded_between_0_and_100():
    rng = np.random.default_rng(42)
    close = pd.Series(100 + np.cumsum(rng.normal(0, 1, 200)))
    result = rsi(close, period=14).dropna()
    assert (result >= 0).all()
    assert (result <= 100).all()


def test_macd_histogram_equals_macd_minus_signal():
    close = pd.Series(np.linspace(100, 150, 100))
    result = macd(close)
    diff = (result["macd"] - result["signal"] - result["histogram"]).abs()
    assert (diff < 1e-9).all()


def test_bollinger_percent_b_near_1_at_local_peak():
    # Gia tang manh dot bien o cuoi -> gan bien tren -> percent_b gan 1.
    close = pd.Series([100.0] * 25 + [130.0])
    result = bollinger_bands(close, period=20, num_std=2.0)
    assert result["percent_b"].iloc[-1] > 0.9


def test_relative_volume_equals_1_when_volume_constant():
    volume = pd.Series([50.0] * 30)
    result = relative_volume(volume, period=20).dropna()
    assert result.round(6).eq(1.0).all()


def test_rolling_volatility_is_zero_for_constant_returns():
    # Gia tang cung 1 ty le % moi buoc -> pct_change khong doi -> std = 0.
    close = pd.Series([100 * (1.01**i) for i in range(30)])
    result = rolling_volatility(close, period=14).dropna()
    assert (result.round(9) == 0).all()


def test_rolling_volatility_is_positive_for_noisy_prices():
    rng = np.random.default_rng(1)
    close = pd.Series(100 + np.cumsum(rng.normal(0, 2, 60)))
    result = rolling_volatility(close, period=14).dropna()
    assert (result > 0).all()
