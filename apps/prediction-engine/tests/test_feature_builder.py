"""
Unit test cho features/feature_builder.py.

Chạy: cd apps/prediction-engine && pytest
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

    # Kiem tra 1 dong bat ky: target_return phai khop % thay doi giua close
    # cua chinh dong do va close cua dong KE TIEP trong df goc.
    idx = df.index[5]
    next_idx = idx + 1
    expected = (klines[next_idx]["close"] - klines[idx]["close"]) / klines[idx]["close"]
    assert df.loc[idx, "target_return"] == pytest.approx(expected)


def test_build_training_frame_drops_last_row_without_target():
    klines = make_klines(100)
    df = build_training_frame(klines)
    # Dong cuoi cung cua chuoi goc khong co "nen ke tiep" de lam target ->
    # phai bi drop, nen index lon nhat con lai < len(klines) - 1.
    assert df.index.max() < len(klines) - 1


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
