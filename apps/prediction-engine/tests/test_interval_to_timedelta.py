"""
Unit test cho main.py::_interval_to_timedelta — dac biet la phan biet "m"
(phut) vs "M" (thang) theo dung quy uoc Binance. Bug thuc te: truoc day ham
nay khong co nhanh rieng cho "M", khien khung thang bi tinh target_time sai
thanh +1 phut (fall qua nhanh mac dinh).

Chạy: cd apps/prediction-engine && pytest
"""

import os
import sys
from datetime import timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from main import _interval_to_timedelta  # noqa: E402


def test_minutes_lowercase_m():
    assert _interval_to_timedelta("1m") == timedelta(minutes=1)
    assert _interval_to_timedelta("15m") == timedelta(minutes=15)


def test_hours():
    assert _interval_to_timedelta("1h") == timedelta(hours=1)


def test_days():
    assert _interval_to_timedelta("1d") == timedelta(days=1)


def test_weeks():
    assert _interval_to_timedelta("1w") == timedelta(weeks=1)


def test_months_uppercase_m_is_not_minutes():
    """1M (thang) phai khac han 1m (phut) — day la bug da tung xay ra."""
    result = _interval_to_timedelta("1M")
    assert result == timedelta(days=30)
    assert result != timedelta(minutes=1)


def test_unknown_unit_falls_back_to_minutes():
    assert _interval_to_timedelta("1x") == timedelta(minutes=1)
