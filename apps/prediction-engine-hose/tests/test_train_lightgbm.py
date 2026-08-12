"""
Unit test cho src/training/train_lightgbm.py::should_deploy() — hàm THUẦN
(không I/O/network/train thật), nhận report dict với key "forecast_zone"
(KHÁC bản crypto dùng key "baseline"). Tham khảo style từ
apps/prediction-engine/tests/test_train_lightgbm.py nhưng sửa đúng API/import
của bản HOSE.

Chạy: cd apps/prediction-engine-hose && python3 -m pytest tests/ -v
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from training.train_lightgbm import (  # noqa: E402
    DIRECTION_REGRESSION_TOLERANCE_PP,
    should_deploy,
)


def make_report(lgbm_mape, naive_mape, fz_mape, lgbm_direction, fz_direction):
    return {
        "lgbm": {"direction_pct": lgbm_direction, "mape": lgbm_mape},
        "naive": {"direction_pct": None, "mape": naive_mape},
        "forecast_zone": {"direction_pct": fz_direction, "mape": fz_mape},
    }


def test_should_deploy_true_when_mape_better_and_direction_tied():
    """Trường hợp thực tế thường gặp: MAPE thắng rõ, direction lệch nhỏ
    (nhiều thống kê) — vẫn được chấp nhận triển khai (xem
    DIRECTION_REGRESSION_TOLERANCE_PP)."""
    report = make_report(
        lgbm_mape=0.044, naive_mape=0.044, fz_mape=0.079, lgbm_direction=49.0, fz_direction=49.3
    )

    deploy, regression_pp = should_deploy(report)

    assert deploy is True
    assert regression_pp == pytest.approx(0.3)


def test_should_deploy_false_when_mape_worse_than_forecast_zone():
    report = make_report(
        lgbm_mape=0.10, naive_mape=0.044, fz_mape=0.079, lgbm_direction=55.0, fz_direction=49.3
    )

    deploy, _ = should_deploy(report)

    assert deploy is False


def test_should_deploy_false_when_mape_worse_than_naive():
    report = make_report(
        lgbm_mape=0.05, naive_mape=0.044, fz_mape=0.079, lgbm_direction=55.0, fz_direction=49.3
    )

    deploy, _ = should_deploy(report)

    assert deploy is False


def test_should_deploy_false_when_direction_regresses_beyond_tolerance():
    report = make_report(
        lgbm_mape=0.04,
        naive_mape=0.044,
        fz_mape=0.079,
        lgbm_direction=40.0,  # kém forecast_zone rất nhiều, vượt ngưỡng cho phép
        fz_direction=49.3,
    )

    deploy, regression_pp = should_deploy(report)

    assert deploy is False
    assert regression_pp > DIRECTION_REGRESSION_TOLERANCE_PP


def test_should_deploy_true_when_lgbm_direction_better_than_forecast_zone():
    # LightGBM thắng cả MAPE và direction (regression_pp âm) -> phải deploy.
    report = make_report(
        lgbm_mape=0.03, naive_mape=0.044, fz_mape=0.079, lgbm_direction=60.0, fz_direction=49.3
    )

    deploy, regression_pp = should_deploy(report)

    assert deploy is True
    assert regression_pp < 0


def test_should_deploy_ignores_direction_check_when_forecast_zone_direction_is_none():
    # forecast_zone không có direction_pct (không đủ lịch sử ở validation) ->
    # direction_regression_pp phải mặc định 0.0 (luôn coi là "trong ngưỡng").
    report = make_report(
        lgbm_mape=0.03, naive_mape=0.044, fz_mape=0.079, lgbm_direction=45.0, fz_direction=None
    )

    deploy, regression_pp = should_deploy(report)

    assert deploy is True
    assert regression_pp == 0.0


def test_should_deploy_ignores_mape_check_when_forecast_zone_mape_is_none():
    # forecast_zone không có mape (fz_errors rỗng) -> chỉ cần thắng naive.
    report = {
        "lgbm": {"direction_pct": 50.0, "mape": 0.03},
        "naive": {"direction_pct": None, "mape": 0.044},
        "forecast_zone": {"direction_pct": None, "mape": None},
    }

    deploy, regression_pp = should_deploy(report)

    assert deploy is True
    assert regression_pp == 0.0


def test_should_deploy_at_exact_tolerance_boundary_is_accepted():
    # regression_pp == DIRECTION_REGRESSION_TOLERANCE_PP (biên) phải VẪN
    # được chấp nhận (<=, không phải <).
    fz_direction = 51.3
    lgbm_direction = fz_direction - DIRECTION_REGRESSION_TOLERANCE_PP
    report = make_report(
        lgbm_mape=0.03, naive_mape=0.044, fz_mape=0.079,
        lgbm_direction=lgbm_direction, fz_direction=fz_direction,
    )

    deploy, regression_pp = should_deploy(report)

    assert regression_pp == pytest.approx(DIRECTION_REGRESSION_TOLERANCE_PP)
    assert deploy is True
