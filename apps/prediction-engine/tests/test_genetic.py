"""
Unit tests cho optimization/genetic.py (Genetic Algorithm toi uu tham so).

Chạy: cd apps/prediction-engine && pytest
"""

import os
import random
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from optimization.genetic import optimize_params, optimize_params_with_validation  # noqa: E402


@pytest.fixture(autouse=True)
def _deterministic_seed():
    # Co dinh seed de test GA (co tinh random) khong flaky.
    random.seed(42)


def test_optimize_params_raises_on_empty_param_sets():
    with pytest.raises(ValueError):
        optimize_params([], fitness_fn=lambda p: 0.0)


def test_optimize_params_never_returns_worse_than_best_seed():
    # Elitism dam bao ca the tot nhat trong seed ban dau khong bao gio bi mat
    # qua cac the he -> ket qua cuoi cung phai >= fitness tot nhat cua seed.
    seed = [{"ema_span": 10, "lookback": 50}, {"ema_span": 20, "lookback": 80}]

    def fitness_fn(params):
        return -(abs(params["ema_span"] - 20) + abs(params["lookback"] - 80))

    best_seed_fitness = max(fitness_fn(p) for p in seed)
    result = optimize_params(seed, fitness_fn, generations=15)

    assert fitness_fn(result) >= best_seed_fitness


def test_optimize_params_converges_towards_known_optimum():
    # Fitness gia lap co 1 vung toi uu duy nhat (ema_span=20, lookback=80),
    # tuong tu bai toan backtest_accuracy thuc te. GA phai tim duoc ca the
    # tot hon ro rang so voi seed ban dau (khong yeu cau trung khop tuyet doi
    # vi thuat toan co tinh random).
    target = {"ema_span": 20, "lookback": 80}

    def fitness_fn(params):
        return -(
            (params["ema_span"] - target["ema_span"]) ** 2
            + (params["lookback"] - target["lookback"]) ** 2
        )

    seed = [{"ema_span": 5, "lookback": 20}, {"ema_span": 45, "lookback": 190}]
    initial_best_fitness = max(fitness_fn(p) for p in seed)

    result = optimize_params(seed, fitness_fn, generations=40)

    assert fitness_fn(result) > initial_best_fitness


def test_optimize_params_respects_param_bounds():
    seed = [{"ema_span": 5, "lookback": 20}]

    result = optimize_params(seed, fitness_fn=lambda p: p["ema_span"], generations=10)

    assert 3 <= result["ema_span"] <= 50
    assert 10 <= result["lookback"] <= 200


def test_optimize_params_preserves_non_tunable_keys():
    # Key khong nam trong PARAM_BOUNDS (vd "label") phai giu nguyen, khong bi
    # dot bien/khoi tao lai ngau nhien.
    seed = [{"ema_span": 10, "lookback": 50, "label": "v1"}]

    result = optimize_params(seed, fitness_fn=lambda p: p["ema_span"], generations=5)

    assert result["label"] == "v1"


def test_optimize_params_single_param_set_still_runs():
    seed = [{"ema_span": 10, "lookback": 50}]

    result = optimize_params(seed, fitness_fn=lambda p: -p["ema_span"], generations=5)

    assert 3 <= result["ema_span"] <= 50


def test_optimize_params_with_validation_accepts_candidate_that_generalizes():
    # Train va validation cung huong toi cung 1 optimum -> ca the moi phai
    # duoc chap nhan (tot hon tham so hien tai tren ca hai).
    seed = [{"ema_span": 10, "lookback": 50}, {"ema_span": 20, "lookback": 80}]

    def make_fitness_fn(target):
        return lambda p: -((p["ema_span"] - target[0]) ** 2 + (p["lookback"] - target[1]) ** 2)

    train_fitness_fn = make_fitness_fn((20, 80))
    validation_fitness_fn = make_fitness_fn((20, 80))

    result = optimize_params_with_validation(
        seed, train_fitness_fn, validation_fitness_fn, generations=30
    )

    assert validation_fitness_fn(result) >= validation_fitness_fn(seed[0])


def test_optimize_params_with_validation_rolls_back_when_overfit():
    # Mo phong overfitting: GA toi uu theo train_fitness_fn (huong ve mot
    # optimum "gia"), nhung validation_fitness_fn (tieu chi thuc su quan
    # trong) lai danh gia cao tham so HIEN TAI hon bat ky ca the nao GA co
    # the tim duoc. -> phai rollback ve param_sets[0], khong duoc chap nhan
    # ca the moi.
    current = {"ema_span": 10, "lookback": 50}
    seed = [current, {"ema_span": 40, "lookback": 150}]

    def train_fitness_fn(p):
        # GA se bi keo ve phia (40, 150) tren train.
        return -((p["ema_span"] - 40) ** 2 + (p["lookback"] - 150) ** 2)

    def validation_fitness_fn(p):
        # Tren validation, CHI co dung tham so hien tai la tot; moi thu khac
        # (bao gom bat ky ca the GA tim duoc) deu te hon ro rang.
        if p == current:
            return 0.0
        return -1000.0

    result = optimize_params_with_validation(
        seed, train_fitness_fn, validation_fitness_fn, generations=20
    )

    assert result == current
