"""
Unit test cho src/features/technical_indicators.py — kiểm tra công thức
đúng hướng (không cần đúng tuyệt đối từng con số, chỉ cần đúng TÍNH CHẤT
toán học cơ bản của từng chỉ báo). Module thuần pandas, không có gì đặc thù
HOSE nên các case tương tự bản crypto (port nguyên vẹn).

Chạy: cd apps/prediction-engine-hose && python3 -m pytest tests/ -v
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
    close = pd.Series(np.arange(1, 50, dtype=float))  # tăng đều, không bao giờ giảm
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


def test_macd_returns_dataframe_with_expected_columns():
    close = pd.Series(np.linspace(100, 150, 60))
    result = macd(close)
    assert list(result.columns) == ["macd", "signal", "histogram"]
    assert len(result) == len(close)


def test_bollinger_percent_b_near_1_at_local_peak():
    # Giá tăng mạnh đột biến ở cuối -> gần biên trên -> percent_b gần 1.
    close = pd.Series([100.0] * 25 + [130.0])
    result = bollinger_bands(close, period=20, num_std=2.0)
    assert result["percent_b"].iloc[-1] > 0.9


def test_bollinger_bandwidth_is_zero_when_price_constant():
    # Giá không đổi -> std = 0 -> upper == lower == middle -> bandwidth = 0.
    close = pd.Series([100.0] * 30)
    result = bollinger_bands(close, period=20, num_std=2.0)
    assert result["bandwidth"].dropna().round(9).eq(0.0).all()


def test_relative_volume_equals_1_when_volume_constant():
    volume = pd.Series([50.0] * 30)
    result = relative_volume(volume, period=20).dropna()
    assert result.round(6).eq(1.0).all()


def test_relative_volume_greater_than_1_on_volume_spike():
    volume = pd.Series([50.0] * 25 + [500.0])
    result = relative_volume(volume, period=20)
    assert result.iloc[-1] > 1.0


def test_rolling_volatility_is_zero_for_constant_returns():
    # Giá tăng cùng 1 tỉ lệ % mỗi bước -> pct_change không đổi -> std = 0.
    close = pd.Series([100 * (1.01**i) for i in range(30)])
    result = rolling_volatility(close, period=14).dropna()
    assert (result.round(9) == 0).all()


def test_rolling_volatility_is_positive_for_noisy_prices():
    rng = np.random.default_rng(1)
    close = pd.Series(100 + np.cumsum(rng.normal(0, 2, 60)))
    result = rolling_volatility(close, period=14).dropna()
    assert (result > 0).all()


def test_all_indicators_preserve_series_length():
    close = pd.Series(np.linspace(100, 120, 50))
    volume = pd.Series(np.full(50, 10.0))

    assert len(rsi(close)) == len(close)
    assert len(macd(close)) == len(close)
    assert len(bollinger_bands(close)) == len(close)
    assert len(relative_volume(volume)) == len(volume)
    assert len(rolling_volatility(close)) == len(close)
