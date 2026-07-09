"""
Unit tests cho cac hang so self-learning trong main.py duoc doc tu bien moi
truong (OPTIMIZE_EVERY_N_EVALUATIONS, MIN_HISTORY_FOR_OPTIMIZE, TRAIN_SPLIT_RATIO,
ACCURACY_HISTORY_MAXLEN, CANDLE_BUFFER_MAXLEN).

Chạy: cd apps/prediction-engine && pytest

Dung importlib.reload de buoc main.py doc lai bien moi truong tai thoi diem
import (cac hang so nay duoc doc 1 lan luc module-level).
"""

import importlib
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import main as main_module  # noqa: E402


@pytest.fixture(autouse=True)
def _reload_main_after_test():
    """Dam bao module main duoc reload lai voi env sach se sau moi test,
    de khong lam anh huong cac test khac (vd test_main_self_learning.py)."""
    yield
    for key in (
        "OPTIMIZE_EVERY_N_EVALUATIONS",
        "MIN_HISTORY_FOR_OPTIMIZE",
        "TRAIN_SPLIT_RATIO",
        "ACCURACY_HISTORY_MAXLEN",
        "CANDLE_BUFFER_MAXLEN",
    ):
        os.environ.pop(key, None)
    importlib.reload(main_module)


def test_optimize_every_n_evaluations_reads_from_env(monkeypatch):
    monkeypatch.setenv("OPTIMIZE_EVERY_N_EVALUATIONS", "5")

    importlib.reload(main_module)

    assert main_module.OPTIMIZE_EVERY_N_EVALUATIONS == 5


def test_min_history_for_optimize_reads_from_env(monkeypatch):
    monkeypatch.setenv("MIN_HISTORY_FOR_OPTIMIZE", "42")

    importlib.reload(main_module)

    assert main_module.MIN_HISTORY_FOR_OPTIMIZE == 42


def test_train_split_ratio_reads_from_env(monkeypatch):
    monkeypatch.setenv("TRAIN_SPLIT_RATIO", "0.55")

    importlib.reload(main_module)

    assert main_module.TRAIN_SPLIT_RATIO == pytest.approx(0.55)


def test_train_split_ratio_out_of_range_raises(monkeypatch):
    monkeypatch.setenv("TRAIN_SPLIT_RATIO", "1.5")

    with pytest.raises(ValueError):
        importlib.reload(main_module)


def test_default_values_when_env_not_set(monkeypatch):
    monkeypatch.delenv("OPTIMIZE_EVERY_N_EVALUATIONS", raising=False)
    monkeypatch.delenv("MIN_HISTORY_FOR_OPTIMIZE", raising=False)
    monkeypatch.delenv("TRAIN_SPLIT_RATIO", raising=False)

    importlib.reload(main_module)

    assert main_module.OPTIMIZE_EVERY_N_EVALUATIONS == 30
    assert main_module.MIN_HISTORY_FOR_OPTIMIZE == 80
    assert main_module.TRAIN_SPLIT_RATIO == pytest.approx(0.7)
