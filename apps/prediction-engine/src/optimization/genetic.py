"""
Genetic Algorithm cho toi uu hoa tham so online.

Theo project_technical_spec.md muc 4.1 & 4.2:
    "Genetic Algorithm: toi uu hoa sieu tham so (learning rate, window size,
    trong so feature) theo chu ky, phu hop bai toan toi uu online khong can
    gradient."

    pseudocode muc 4.2:
        new_params = genetic_algorithm.evolve(
            population=current_param_sets,
            fitness_fn=lambda p: backtest_accuracy(p, recent_history)
        )

Trien khai:
    - Selection: tournament selection tren quan the da xep hang theo fitness.
    - Crossover: uniform crossover (moi key lay tu 1 trong 2 parent).
    - Mutation: dot bien ngau nhien, GIOI HAN bien do (mutation_step) va gioi
      han tuyet doi (PARAM_BOUNDS) de tranh "thrashing" nhu canh bao muc 4.4
      cua spec.
    - Elitism: giu lai `elite_count` ca the tot nhat qua cac the he.
    - Dieu kien dung: `generations` toi da HOAC hoi tu (khong cai thien fitness
      qua `convergence_patience` the he lien tiep).

Rollback / circuit breaker (muc 4.4: neu accuracy giam lien tuc, rollback ve
model_params_history gan nhat co accuracy cao) KHONG thuoc pham vi ham thuan
tuy nay — no can truy cap lich su da luu (model_params_history), nen se do
caller (main.py / vong lap self-learning) dam nhiem khi tich hop optimize_params
o day.
"""

from __future__ import annotations

import random
from typing import Any, Callable, Sequence

ParamSet = dict[str, Any]
FitnessFn = Callable[[ParamSet], float]

# Gioi han tuyet doi cho tung tham so — dot bien/khoi tao ngau nhien khong
# duoc vuot ra ngoai day (tranh sinh ra tham so vo nghia, vd ema_span <= 0).
PARAM_BOUNDS: dict[str, tuple[int, int]] = {
    "ema_span": (3, 50),
    "lookback": (10, 200),
}

DEFAULT_POPULATION_SIZE = 12
DEFAULT_GENERATIONS = 20
DEFAULT_MUTATION_RATE = 0.3
# Ti le (so voi bien do [lo, hi]) cho phep dot bien nhay toi da moi lan —
# gioi han bien do dieu chinh de tranh dao dong manh giua cac vong toi uu.
DEFAULT_MUTATION_STEP = 0.2
DEFAULT_ELITE_COUNT = 2
DEFAULT_TOURNAMENT_SIZE = 3
# So the he lien tiep khong cai thien best fitness truoc khi coi la hoi tu.
DEFAULT_CONVERGENCE_PATIENCE = 5


def _clip_param(name: str, value: float) -> int:
    lo, hi = PARAM_BOUNDS.get(name, (value, value))
    return int(max(lo, min(hi, round(value))))


def _random_param_set(template: ParamSet) -> ParamSet:
    """Khoi tao ngau nhien 1 ca the moi, dung cung tap key voi `template`."""
    result: ParamSet = {}
    for key, value in template.items():
        if key in PARAM_BOUNDS:
            lo, hi = PARAM_BOUNDS[key]
            result[key] = random.randint(lo, hi)
        else:
            result[key] = value
    return result


def _crossover(parent_a: ParamSet, parent_b: ParamSet) -> ParamSet:
    """Uniform crossover: moi key duoc lay tu parent_a hoac parent_b (50/50)."""
    return {
        key: (parent_a[key] if random.random() < 0.5 else parent_b[key])
        for key in parent_a
    }


def _mutate(individual: ParamSet, mutation_rate: float, mutation_step: float) -> ParamSet:
    """Dot bien tung key doc lap voi xac suat `mutation_rate`, bien do gioi han."""
    mutated = dict(individual)
    for key, value in individual.items():
        if key not in PARAM_BOUNDS:
            continue
        if random.random() >= mutation_rate:
            continue
        lo, hi = PARAM_BOUNDS[key]
        span = hi - lo
        delta = random.uniform(-mutation_step, mutation_step) * span
        mutated[key] = _clip_param(key, value + delta)
    return mutated


def _tournament_select(ranked_population: list[ParamSet], tournament_size: int) -> ParamSet:
    """
    Chon 1 ca the bang tournament selection.

    `ranked_population` phai da duoc sap xep giam dan theo fitness (chi so 0
    la ca the tot nhat). Lay ngau nhien `tournament_size` chi so, tra ve ca
    the co chi so nho nhat (tot nhat) trong nhom duoc chon.
    """
    size = min(tournament_size, len(ranked_population))
    contestant_indices = random.sample(range(len(ranked_population)), size)
    best_index = min(contestant_indices)
    return ranked_population[best_index]


def optimize_params(
    param_sets: Sequence[ParamSet],
    fitness_fn: FitnessFn,
    population_size: int = DEFAULT_POPULATION_SIZE,
    generations: int = DEFAULT_GENERATIONS,
    mutation_rate: float = DEFAULT_MUTATION_RATE,
    mutation_step: float = DEFAULT_MUTATION_STEP,
    elite_count: int = DEFAULT_ELITE_COUNT,
    tournament_size: int = DEFAULT_TOURNAMENT_SIZE,
    convergence_patience: int = DEFAULT_CONVERGENCE_PATIENCE,
) -> ParamSet:
    """
    Tien hoa `param_sets` (quan the ban dau) qua nhieu the he de toi da hoa
    `fitness_fn`, vd `lambda p: backtest_accuracy(p, recent_history)`.

    Args:
        param_sets: quan the ban dau (it nhat 1 ca the). Cac key cua ca the
                    dau tien duoc dung lam "khuon" cho toan bo qua trinh tien
                    hoa (key nao co trong PARAM_BOUNDS moi duoc dot bien/khoi
                    tao ngau nhien, key khac giu nguyen gia tri parent).
        fitness_fn: ham danh gia do "fit" — fitness CANG CAO CANG TOT.
        population_size: kich thuoc quan the moi the he (mac dinh 12).
        generations: so the he toi da (mac dinh 20).
        mutation_rate: xac suat dot bien tung tham so cua 1 ca the (0..1).
        mutation_step: bien do dot bien toi da, ti le theo [lo, hi] cua tham so.
        elite_count: so ca the tot nhat duoc giu nguyen qua moi the he.
        tournament_size: so ca the canh tranh moi lan tournament selection.
        convergence_patience: dung som neu qua nhieu the he lien tiep khong
                               cai thien best fitness (hoi tu).

    Returns:
        ParamSet: ca the tot nhat tim duoc (fitness cao nhat qua tat ca the he).

    Raises:
        ValueError: neu param_sets rong.
    """
    if not param_sets:
        raise ValueError("optimize_params: param_sets khong duoc rong.")

    population = list(param_sets)
    template = population[0]
    while len(population) < population_size:
        population.append(_random_param_set(template))
    population = population[:population_size]

    best_individual = population[0]
    best_fitness = fitness_fn(best_individual)
    stagnant_generations = 0

    for _generation in range(generations):
        scored = [(individual, fitness_fn(individual)) for individual in population]
        scored.sort(key=lambda pair: pair[1], reverse=True)

        if scored[0][1] > best_fitness:
            best_individual, best_fitness = scored[0]
            stagnant_generations = 0
        else:
            stagnant_generations += 1

        if stagnant_generations >= convergence_patience:
            break

        ranked_population = [individual for individual, _ in scored]
        next_population = list(ranked_population[:elite_count])

        while len(next_population) < population_size:
            parent_a = _tournament_select(ranked_population, tournament_size)
            parent_b = _tournament_select(ranked_population, tournament_size)
            child = _crossover(parent_a, parent_b)
            child = _mutate(child, mutation_rate, mutation_step)
            next_population.append(child)

        population = next_population

    return best_individual


def optimize_params_with_validation(
    param_sets: Sequence[ParamSet],
    train_fitness_fn: FitnessFn,
    validation_fitness_fn: FitnessFn,
    **optimize_kwargs: Any,
) -> ParamSet:
    """
    Nhu `optimize_params`, nhung them 1 buoc validation truoc khi chap nhan
    ket qua moi — implement "walk-forward validation" + "circuit breaker" o
    muc 4.4 project_technical_spec.md.

    Ly do can ham nay: thu nghiem thuc te (backtest tren du lieu BTCUSDT
    thuc) cho thay GA CO THE tim duoc ema_span/lookback toi uu tren tap train
    nhung ket qua khong generalize — hieu suat tren tap validation (du lieu
    GA chua tung thay) lai KEM HON tham so mac dinh ban dau. Day la overfitting
    kinh dien, dung tach rieng validation moi phat hien duoc.

    Quy trinh:
        1. Chay optimize_params() nhu thuong, toi uu theo `train_fitness_fn`.
        2. Danh gia ca the "hien tai" (param_sets[0]) va ca the moi tim duoc
           TREN `validation_fitness_fn` (du lieu / tieu chi khac train).
        3. Chi chap nhan ca the moi neu no >= hien tai tren validation. Neu
           khong, ROLLBACK ve param_sets[0] (giu nguyen tham so cu) — dung
           chinh cach circuit breaker duoc mo ta trong spec.

    Args:
        param_sets: quan the ban dau; param_sets[0] duoc coi la "tham so
                    hien tai dang dung" (moc rollback).
        train_fitness_fn: fitness dung de tien hoa (vd backtest tren tap train).
        validation_fitness_fn: fitness dung de KIEM TRA ket qua (vd backtest
                                tren tap validation/out-of-sample rieng biet,
                                hoac chinh tap train neu chi muon so sanh don
                                gian — nhung khuyen nghi dung du lieu khac).
        **optimize_kwargs: cac tham so bo sung chuyen tiep cho optimize_params
                            (population_size, generations, mutation_rate, ...).

    Returns:
        ParamSet: ca the moi neu no >= param_sets[0] tren validation, nguoc
                  lai tra ve param_sets[0] khong doi (rollback).
    """
    current = param_sets[0]
    candidate = optimize_params(param_sets, train_fitness_fn, **optimize_kwargs)

    if validation_fitness_fn(candidate) >= validation_fitness_fn(current):
        return candidate
    return current
