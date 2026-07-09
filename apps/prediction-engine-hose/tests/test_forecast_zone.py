"""Unit test cho src/forecast_zone.py — builder vùng giá HOSE."""

import os
import sys
from datetime import date

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from forecast_zone import build_forecast_zone  # noqa: E402
from price_limit import funnel_bounds  # noqa: E402


def _flat_history(price, n=30):
    """Lịch sử giá đi ngang (dùng kiểm tra tính chất, không phải mock production)."""
    return [{"open": price, "high": price * 1.01, "low": price * 0.99, "close": price} for _ in range(n)]


def _uptrend_history(start=100.0, step=0.02, n=30):
    hist = []
    p = start
    for _ in range(n):
        hist.append({"open": p, "high": p * 1.01, "low": p * 0.99, "close": p})
        p *= 1 + step
    return hist


def test_raises_when_history_too_short():
    with pytest.raises(ValueError):
        build_forecast_zone([{"open": 1, "high": 1, "low": 1, "close": 1}], n_steps=5)


def test_raises_when_n_steps_invalid():
    with pytest.raises(ValueError):
        build_forecast_zone(_flat_history(100), n_steps=0)


def test_produces_n_predictions():
    zone = build_forecast_zone(_flat_history(100), n_steps=5)
    assert len(zone["predictions"]) == 5
    assert zone["ref_close"] == 100.0


def test_all_steps_within_funnel():
    zone = build_forecast_zone(_uptrend_history(), n_steps=5)
    ref = zone["ref_close"]
    for row in zone["predictions"]:
        floor, ceiling = funnel_bounds(ref, row["step"])
        # Cho sai số số học nhỏ.
        assert row["predicted_high"] <= ceiling + 1e-6
        assert row["predicted_low"] >= floor - 1e-6
        assert row["predicted_low"] <= row["predicted_high"]


def test_funnel_widens_over_steps():
    zone = build_forecast_zone(_uptrend_history(), n_steps=5)
    p = zone["predictions"]
    # Trần của bước sau cao hơn bước trước (phễu nở).
    assert p[-1]["ceiling"] > p[0]["ceiling"]
    assert p[-1]["floor"] < p[0]["floor"]


def test_confidence_decays():
    zone = build_forecast_zone(_flat_history(100), n_steps=5)
    confs = [r["confidence"] for r in zone["predictions"]]
    assert all(confs[i] >= confs[i + 1] for i in range(len(confs) - 1))


def test_uptrend_gives_positive_upper_zone():
    zone = build_forecast_zone(_uptrend_history(step=0.03), n_steps=5)
    # Xu hướng tăng -> biên trên vùng dương và lớn.
    assert zone["zone_upper_pct"] > 0


def test_target_dates_attached():
    dates = [date(2026, 7, 10), date(2026, 7, 13), date(2026, 7, 14)]
    zone = build_forecast_zone(_flat_history(100), n_steps=3, target_dates=dates)
    assert zone["predictions"][0]["target_time"] == "2026-07-10"
    assert zone["predictions"][2]["target_time"] == "2026-07-14"


def test_target_dates_length_must_match():
    with pytest.raises(ValueError):
        build_forecast_zone(_flat_history(100), n_steps=3, target_dates=[date(2026, 7, 10)])


def test_upper_zone_never_exceeds_cumulative_limit():
    # Xu hướng tăng cực mạnh -> vẫn phải bị phễu ±7%/phiên chặn.
    zone = build_forecast_zone(_uptrend_history(step=0.20), n_steps=5)
    # Sau 5 phiên, trần lũy tiến = (1.07^5 - 1) ~ 40.25%.
    max_theoretical = (1.07 ** 5 - 1) * 100
    assert zone["zone_upper_pct"] <= max_theoretical + 1e-6
