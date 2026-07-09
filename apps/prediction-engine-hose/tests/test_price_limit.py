"""Unit test cho src/price_limit.py — phễu trần/sàn HOSE ±7%."""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from price_limit import (  # noqa: E402
    HOSE_DAILY_LIMIT,
    clamp,
    clamp_forecast_step,
    daily_band,
    funnel_bounds,
    pct_change,
)


def test_daily_band_is_plus_minus_7_percent():
    floor, ceiling = daily_band(100.0)
    assert floor == pytest.approx(93.0)
    assert ceiling == pytest.approx(107.0)


def test_daily_band_rejects_non_positive():
    with pytest.raises(ValueError):
        daily_band(0)


def test_funnel_widens_each_step():
    f1, c1 = funnel_bounds(100.0, 1)
    f2, c2 = funnel_bounds(100.0, 2)
    # Phễu nở dần: bước 2 rộng hơn bước 1.
    assert c2 > c1 > 100.0
    assert f2 < f1 < 100.0
    # Đúng công thức lũy tiến (1±0.07)^k.
    assert c2 == pytest.approx(100.0 * (1 + HOSE_DAILY_LIMIT) ** 2)
    assert f2 == pytest.approx(100.0 * (1 - HOSE_DAILY_LIMIT) ** 2)


def test_funnel_bounds_rejects_bad_args():
    with pytest.raises(ValueError):
        funnel_bounds(100.0, 0)
    with pytest.raises(ValueError):
        funnel_bounds(0, 1)


def test_clamp_forecast_step_caps_into_funnel():
    # Model dự đoán vượt biên (high 130, low 60) ở phiên t+1 quanh ref 100
    # -> phải kẹp vào [93, 107].
    result = clamp_forecast_step(
        predicted_low=60.0,
        predicted_high=130.0,
        predicted_close=125.0,
        ref_close=100.0,
        step=1,
    )
    assert result["ceiling"] == pytest.approx(107.0)
    assert result["floor"] == pytest.approx(93.0)
    assert result["predicted_high"] == pytest.approx(107.0)  # bị trần chặn
    assert result["predicted_low"] == pytest.approx(93.0)     # bị sàn chặn
    assert result["predicted_close"] == pytest.approx(107.0)  # cũng bị trần chặn


def test_clamp_forecast_step_keeps_values_inside_funnel():
    # Dự đoán nằm trong biên -> giữ nguyên.
    result = clamp_forecast_step(
        predicted_low=98.0,
        predicted_high=104.0,
        predicted_close=102.0,
        ref_close=100.0,
        step=1,
    )
    assert result["predicted_low"] == pytest.approx(98.0)
    assert result["predicted_high"] == pytest.approx(104.0)
    assert result["predicted_close"] == pytest.approx(102.0)


def test_clamp_helper():
    assert clamp(5, 0, 10) == 5
    assert clamp(-3, 0, 10) == 0
    assert clamp(99, 0, 10) == 10


def test_pct_change():
    assert pct_change(110.0, 100.0) == pytest.approx(10.0)
    assert pct_change(93.0, 100.0) == pytest.approx(-7.0)
