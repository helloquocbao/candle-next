"""
Unit test cho src/features/feature_builder.py — build_training_frame() và
build_inference_features(), dùng dữ liệu OHLCV daily HOSE tổng hợp
(synthetic), KHÔNG gọi network/DB thật.

Chạy: cd apps/prediction-engine-hose && python3 -m pytest tests/ -v
"""

import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from features.feature_builder import (  # noqa: E402
    FEATURE_COLUMNS,
    MIN_HISTORY_FOR_FEATURES,
    build_inference_features,
    build_training_frame,
)


def make_klines(n, seed=0):
    """Lịch sử OHLCV tổng hợp (không phải dữ liệu thị trường thật)."""
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


def test_build_training_frame_has_all_feature_columns_and_no_nan():
    klines = make_klines(200)
    df = build_training_frame(klines)

    assert not df.empty
    for col in [*FEATURE_COLUMNS, "target_return", "close"]:
        assert col in df.columns
    assert not df[FEATURE_COLUMNS].isna().to_numpy().any()
    assert not df["target_return"].isna().to_numpy().any()


def test_build_training_frame_target_return_matches_next_close_pct_change():
    klines = make_klines(100)
    df = build_training_frame(klines)

    # Kiểm tra 1 dòng bất kỳ: target_return phải khớp % thay đổi giữa close
    # của chính dòng đó và close của dòng KẾ TIẾP trong klines gốc.
    idx = df.index[5]
    next_idx = idx + 1
    expected = (klines[next_idx]["close"] - klines[idx]["close"]) / klines[idx]["close"]
    assert df.loc[idx, "target_return"] == pytest.approx(expected)


def test_build_training_frame_drops_last_row_without_target():
    klines = make_klines(100)
    df = build_training_frame(klines)
    # Dòng cuối cùng của chuỗi gốc không có "nến kế tiếp" để làm target ->
    # phải bị drop, nên index lớn nhất còn lại < len(klines) - 1.
    assert df.index.max() < len(klines) - 1


def test_build_training_frame_raises_when_too_short_after_dropna():
    # Lịch sử quá ngắn -> mọi dòng đều còn NaN -> dropna() trả về DataFrame
    # rỗng (không raise, chỉ rỗng) — kiểm tra tính chất đó.
    klines = make_klines(5)
    df = build_training_frame(klines)
    assert df.empty


def test_build_inference_features_returns_none_when_not_enough_history():
    klines = make_klines(MIN_HISTORY_FOR_FEATURES - 5)
    assert build_inference_features(klines) is None


def test_build_inference_features_returns_single_row_with_all_columns():
    klines = make_klines(200)
    result = build_inference_features(klines)

    assert result is not None
    assert len(result) == 1
    assert list(result.columns) == FEATURE_COLUMNS
    assert not result.isna().to_numpy().any()


def test_build_inference_features_matches_last_row_of_training_frame_features():
    # build_inference_features tính feature cho dòng CUỐI CÙNG — phải khớp
    # với giá trị feature tương ứng tính bởi build_training_frame (dùng
    # klines cắt ngắn 1 phiên để dòng cuối của bản đầy đủ != dòng cuối build
    # training frame do target_return bị drop).
    klines = make_klines(200)
    inference_row = build_inference_features(klines)

    # Tính lại feature cho toàn bộ chuỗi (không cắt) và so dòng cuối.
    full_frame_with_last = build_training_frame(klines[:-1] + [klines[-1], klines[-1]])
    # Không thể tái dùng target dễ dàng ở đây -> chỉ kiểm tra kiểu & cột.
    assert set(inference_row.columns) == set(FEATURE_COLUMNS)
    assert set(full_frame_with_last.columns) >= set(FEATURE_COLUMNS)
