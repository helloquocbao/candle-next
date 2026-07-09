"""
Unit test cho features/market_regime.py — kiểm tra module phân loại đúng
TÍNH CHẤT của từng trạng thái thị trường trên dữ liệu tổng hợp có chủ đích
(không cần đúng nhãn tuyệt đối trong vùng biên, chỉ cần đúng bản chất).

Chạy: cd apps/prediction-engine && pytest
"""

import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from features.market_regime import (  # noqa: E402
    MIN_HISTORY_FOR_REGIME,
    detect_regime,
)


def _make_klines(closes, volumes=None):
    """Dựng list nến OHLCV tối giản từ chuỗi giá close (high/low quanh close)."""
    volumes = volumes if volumes is not None else [100.0] * len(closes)
    klines = []
    for c, v in zip(closes, volumes):
        klines.append(
            {
                "open": c,
                "high": c * 1.001,
                "low": c * 0.999,
                "close": c,
                "volume": v,
            }
        )
    return klines


def test_returns_unknown_when_not_enough_history():
    klines = _make_klines([100.0] * (MIN_HISTORY_FOR_REGIME - 1))
    result = detect_regime(klines)
    assert result["regime"] == "UNKNOWN"
    assert result["confidence_modifier"] == 1.0


def test_empty_history_is_unknown():
    assert detect_regime([])["regime"] == "UNKNOWN"


def test_strong_uptrend_detected():
    # Giá tăng đều, mượt -> R^2 cao + drift dương lớn.
    closes = [100.0 * (1.01**i) for i in range(60)]
    result = detect_regime(_make_klines(closes))
    assert result["regime"] in ("UPTREND", "STRONG_UPTREND")
    assert result["trend"] == "up"
    assert result["drift_pct"] > 0
    assert result["confidence_modifier"] >= 1.0


def test_strong_downtrend_detected():
    closes = [100.0 * (0.99**i) for i in range(60)]
    result = detect_regime(_make_klines(closes))
    assert result["regime"] in ("DOWNTREND", "STRONG_DOWNTREND")
    assert result["trend"] == "down"
    assert result["drift_pct"] < 0


def test_ranging_market_low_drift():
    # Dao động nhỏ quanh 1 mức, không xu hướng -> RANGING (hoặc SQUEEZE nếu
    # biên quá hẹp) nhưng chắc chắn KHÔNG phải trend.
    rng = np.random.default_rng(7)
    closes = list(100 + rng.normal(0, 0.3, 60))
    result = detect_regime(_make_klines(closes))
    assert result["regime"] in ("RANGING", "SQUEEZE", "VOLATILE")
    assert result["regime"] not in ("UPTREND", "STRONG_UPTREND", "DOWNTREND", "STRONG_DOWNTREND")


def test_output_has_all_expected_keys():
    closes = [100.0 + i * 0.1 for i in range(60)]
    result = detect_regime(_make_klines(closes))
    for key in (
        "regime",
        "trend",
        "trend_strength",
        "drift_pct",
        "volatility_level",
        "momentum",
        "rsi",
        "volume_state",
        "confidence_modifier",
        "summary",
    ):
        assert key in result
    assert 0.0 <= result["trend_strength"] <= 1.0
    assert isinstance(result["summary"], str) and result["summary"]


def test_high_volume_breakout_flagged_as_high_volume():
    # Volume nến cuối tăng vọt -> volume_state = high.
    closes = [100.0 + i * 0.2 for i in range(60)]
    volumes = [100.0] * 59 + [500.0]
    result = detect_regime(_make_klines(closes, volumes))
    assert result["volume_state"] == "high"


def test_never_raises_on_string_ohlcv():
    # ingestion đôi khi đưa số dạng chuỗi -> module phải cast an toàn.
    closes = [str(100.0 + i * 0.1) for i in range(60)]
    klines = [
        {"open": c, "high": c, "low": c, "close": c, "volume": "100"} for c in closes
    ]
    result = detect_regime(klines)
    assert result["regime"] != "UNKNOWN"
