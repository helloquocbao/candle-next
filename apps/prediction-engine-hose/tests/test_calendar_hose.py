"""Unit test cho src/calendar_hose.py — lịch phiên HOSE."""

import os
import sys
from datetime import date, datetime

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from calendar_hose import (  # noqa: E402
    is_after_close,
    is_trading_day,
    is_weekend,
    next_n_trading_days,
    next_trading_day,
)


def test_weekend_detection():
    assert is_weekend(date(2026, 7, 11))  # thứ 7
    assert is_weekend(date(2026, 7, 12))  # chủ nhật
    assert not is_weekend(date(2026, 7, 9))  # thứ 5


def test_is_trading_day_excludes_weekend():
    assert is_trading_day(date(2026, 7, 9))       # thứ 5 -> có
    assert not is_trading_day(date(2026, 7, 11))  # thứ 7 -> không


def test_is_trading_day_excludes_holiday():
    holiday = date(2026, 9, 2)  # Quốc khánh (ví dụ)
    assert not is_trading_day(holiday, holidays={holiday})


def test_next_trading_day_skips_weekend():
    # Thứ 6 (2026-07-10) -> ngày giao dịch kế tiếp là thứ 2 (2026-07-13).
    assert next_trading_day(date(2026, 7, 10)) == date(2026, 7, 13)


def test_next_trading_day_skips_holiday():
    # Thứ 5 -> thứ 6 là nghỉ lễ -> nhảy sang thứ 2.
    holidays = {date(2026, 7, 10)}
    assert next_trading_day(date(2026, 7, 9), holidays) == date(2026, 7, 13)


def test_next_n_trading_days_returns_business_days():
    # Từ thứ 5 (2026-07-09), 5 phiên tới: 10(T6),13,14,15,16.
    days = next_n_trading_days(date(2026, 7, 9), 5)
    assert days == [
        date(2026, 7, 10),
        date(2026, 7, 13),
        date(2026, 7, 14),
        date(2026, 7, 15),
        date(2026, 7, 16),
    ]


def test_next_n_trading_days_rejects_bad_n():
    with pytest.raises(ValueError):
        next_n_trading_days(date(2026, 7, 9), 0)


def test_is_after_close():
    assert is_after_close(datetime(2026, 7, 9, 15, 0))   # 15:00 -> đã đóng cửa
    assert not is_after_close(datetime(2026, 7, 9, 10, 0))  # 10:00 -> đang giao dịch
