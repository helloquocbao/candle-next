"""
Train model LightGBM du doan % thay doi gia (return) cua nen ke tiep, cho 1
cap symbol/interval cu the. Danh gia tren tap validation (time-based split,
KHONG random — tranh lookahead bias) va so sanh trung thuc voi 2 muc doi
chieu, TACH RIENG 2 loai chi so (khong tron lan):

  - MAPE (sai so gia): so voi "naive" (du doan khong doi, predicted_close =
    close hien tai) VA baseline EMA — ca 2 deu la muc so sanh hop le cho
    MAPE vi ca 2 co gia tri du doan cu the de tinh sai so.

  - Direction accuracy: CHI so voi baseline EMA va muc 50% (tung xu ngau
    nhien), KHONG so voi naive — vi naive luon du doan "khong doi"
    (predicted_direction = 0), ma evaluation/accuracy.py::compute_accuracy
    so sanh CHIEU theo DAU (sign), nen naive gan nhu LUON bi tinh "sai
    chieu" (gia thuc te gan nhu khong bao gio dung yen tuyet doi) — day la
    hanh vi DUNG cua ham so sanh (sua 1 bug cu tung lam naive "luon dung"),
    nhung dieu do dong nghia "naive direction accuracy" la 1 con so VO
    NGHIA de lam moc so sanh (se luon ~0%, khong phan anh chat luong thi
    truong hay model nao ca).

Tieu chi trien khai (xac nhan voi chu du an sau khi chay thu tren BTCUSDT/1m
that): model duoc luu neu vuot qua baseline EMA VE MAPE (sai so gia — day la
loi ich chinh, giup vung gia du doan tren chart hep/chinh xac hon), va
KHONG te hon baseline qua DIRECTION_REGRESSION_TOLERANCE_PP diem % ve
direction accuracy (chap nhan hoa/nhieu thong ke o muc do nho — voi 1 phut,
direction accuracy ca 2 model deu dao dong quanh 50%, chenh vai phan muoi %
la nhieu chu khong phai model te hon that su).

Chay thu cong (khong nam trong vong lap chinh cua service):
    cd apps/prediction-engine
    python -m training.train_lightgbm BTCUSDT 1m
"""

from __future__ import annotations

import argparse
import logging
import os
import sys

import lightgbm as lgb
import numpy as np

sys.path.append(__file__.rsplit("/", 2)[0])

from db import get_recent_klines  # noqa: E402
from evaluation.accuracy import compute_accuracy  # noqa: E402
from features.feature_builder import FEATURE_COLUMNS, build_training_frame  # noqa: E402
from models import lightgbm_model  # noqa: E402
from models.baseline import predict_next_candle as baseline_predict_next_candle  # noqa: E402

logging.basicConfig(level="INFO", format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("train_lightgbm")

VALIDATION_FRACTION = 0.2
# Direction accuracy o khung 1 phut dao dong quanh 50% (tung xu) cho ca
# baseline lan LightGBM — chenh lech vai phan muoi diem % la NHIEU THONG KE,
# khong phai model te hon that su (xem docstring dau file). Cho phep LightGBM
# kem hon baseline toi da bao nhieu diem % ve direction ma VAN duoc chap
# nhan trien khai, MIEN LA thang ro ve MAPE (loi ich chinh: vung gia du doan
# hep/chinh xac hon).
DIRECTION_REGRESSION_TOLERANCE_PP = 2.0
LGBM_PARAMS = {
    "objective": "regression",
    "metric": "mae",
    "learning_rate": 0.05,
    "num_leaves": 15,
    "min_data_in_leaf": 20,
    "verbose": -1,
}


def _evaluate_on_validation(klines: list[dict], val_frame, predicted_returns) -> dict:
    """
    So sanh LightGBM vs naive vs baseline EMA TREN CUNG 1 tap validation.

    `val_frame.index` la vi tri THAT trong `klines` goc (pandas giu nguyen
    index goc qua .dropna(), xem features/feature_builder.py) — dung truc
    tiep de cat lich su dung cho baseline_predict_next_candle() tai TUNG
    thoi diem trong validation set, khong bi lech do warmup/NaN da bi drop.
    """
    lgbm_errors, naive_errors, baseline_errors = [], [], []
    lgbm_hits, naive_hits, baseline_hits = 0, 0, 0

    for i, klines_idx in enumerate(val_frame.index):
        klines_idx = int(klines_idx)
        current_close = float(klines[klines_idx]["close"])
        actual = {"close": float(klines[klines_idx + 1]["close"])}

        lgbm_pred_close = current_close * (1.0 + float(predicted_returns[i]))
        result = compute_accuracy(actual, {"predicted_close": lgbm_pred_close}, previous_close=current_close)
        lgbm_errors.append(result["error_pct"])
        lgbm_hits += int(result["direction_correct"])

        naive_result = compute_accuracy(actual, {"predicted_close": current_close}, previous_close=current_close)
        naive_errors.append(naive_result["error_pct"])
        naive_hits += int(naive_result["direction_correct"])

        try:
            baseline_pred = baseline_predict_next_candle(klines[: klines_idx + 1])
            baseline_result = compute_accuracy(actual, baseline_pred, previous_close=current_close)
            baseline_errors.append(baseline_result["error_pct"])
            baseline_hits += int(baseline_result["direction_correct"])
        except ValueError:
            continue  # chua du lich su cho baseline o nhung diem rat dau chuoi

    n = len(val_frame)
    return {
        "n": n,
        "lgbm": {"direction_pct": 100 * lgbm_hits / n, "mape": float(np.mean(lgbm_errors))},
        "naive": {"direction_pct": 100 * naive_hits / n, "mape": float(np.mean(naive_errors))},
        "baseline": {
            "direction_pct": 100 * baseline_hits / len(baseline_errors) if baseline_errors else None,
            "mape": float(np.mean(baseline_errors)) if baseline_errors else None,
        },
    }


def should_deploy(report: dict) -> tuple[bool, float]:
    """
    Quyet dinh model co dat tieu chi trien khai hay khong (xem docstring dau
    file ve ly do tach rieng MAPE/direction). Tach thanh ham thuan (khong
    goi I/O) de test duoc ma khong can train that.

    Returns:
        (deploy: bool, direction_regression_pp: float) — direction_regression_pp
        duong nghia LightGBM kem hon baseline bay nhieu diem %, am nghia tot hon.
    """
    beats_naive_mape = report["lgbm"]["mape"] <= report["naive"]["mape"]
    beats_baseline_mape = report["baseline"]["mape"] is None or report["lgbm"]["mape"] <= report["baseline"]["mape"]
    direction_regression_pp = (
        0.0
        if report["baseline"]["direction_pct"] is None
        else report["baseline"]["direction_pct"] - report["lgbm"]["direction_pct"]
    )
    direction_acceptable = direction_regression_pp <= DIRECTION_REGRESSION_TOLERANCE_PP

    deploy = beats_naive_mape and beats_baseline_mape and direction_acceptable
    return deploy, direction_regression_pp


def train_and_evaluate(symbol: str, interval: str, history_limit: int = 10000) -> None:
    klines = get_recent_klines(symbol, interval, limit=history_limit)
    if len(klines) < 200:
        logger.error(
            "Chi co %d nen lich su cho %s %s — qua it de train co y nghia. "
            "Chay training.backfill_history truoc.",
            len(klines),
            symbol,
            interval,
        )
        return
    logger.info("Da tai %d nen lich su cho %s %s", len(klines), symbol, interval)

    frame = build_training_frame(klines)
    logger.info("Ma tran feature: %d dong (sau khi bo warmup/NaN)", len(frame))

    split_idx = int(len(frame) * (1 - VALIDATION_FRACTION))
    train_frame = frame.iloc[:split_idx]
    val_frame = frame.iloc[split_idx:]

    train_dataset = lgb.Dataset(
        train_frame[FEATURE_COLUMNS].to_numpy(),
        label=train_frame["target_return"].to_numpy(),
        feature_name=FEATURE_COLUMNS,
    )
    val_dataset = lgb.Dataset(
        val_frame[FEATURE_COLUMNS].to_numpy(),
        label=val_frame["target_return"].to_numpy(),
        feature_name=FEATURE_COLUMNS,
        reference=train_dataset,
    )

    booster = lgb.train(
        LGBM_PARAMS,
        train_dataset,
        num_boost_round=500,
        valid_sets=[val_dataset],
        callbacks=[lgb.early_stopping(stopping_rounds=30, verbose=False)],
    )

    predicted_returns = booster.predict(
        val_frame[FEATURE_COLUMNS].to_numpy(), num_iteration=booster.best_iteration
    )
    report = _evaluate_on_validation(klines, val_frame, predicted_returns)

    logger.info("=== Ket qua tren tap validation (%d mau, %s %s) ===", report["n"], symbol, interval)
    logger.info(
        "LightGBM    : direction accuracy=%.2f%%  MAPE=%.4f%%",
        report["lgbm"]["direction_pct"],
        report["lgbm"]["mape"],
    )
    logger.info(
        "Naive       : MAPE=%.4f%%  (direction accuracy KHONG tinh — naive luon du doan "
        "'khong doi' nen luon bi tinh sai chieu theo cach so sanh dau, xem docstring dau file)",
        report["naive"]["mape"],
    )
    if report["baseline"]["direction_pct"] is not None:
        logger.info(
            "Baseline EMA: direction accuracy=%.2f%%  MAPE=%.4f%%",
            report["baseline"]["direction_pct"],
            report["baseline"]["mape"],
        )
    logger.info("(Tung xu ngau nhien = 50%% direction accuracy — moc tham chieu tuyet doi)")

    deploy, direction_regression_pp = should_deploy(report)

    if not deploy:
        logger.warning(
            "LightGBM KHONG dat tieu chi trien khai (MAPE phai <= naive va baseline, "
            "direction khong duoc kem baseline qua %.1f diem %%) — KHONG luu model nay. "
            "Can them feature/du lieu/tuning truoc khi thu lai.",
            DIRECTION_REGRESSION_TOLERANCE_PP,
        )
        return

    os.makedirs(lightgbm_model.MODELS_DIR, exist_ok=True)
    save_path = lightgbm_model.model_path(symbol, interval)
    booster.save_model(save_path)
    logger.info(
        "Model dat tieu chi trien khai (MAPE tot hon naive+baseline, direction lech %.2f diem %% "
        "trong nguong cho phep %.1f) — da luu vao %s",
        direction_regression_pp,
        DIRECTION_REGRESSION_TOLERANCE_PP,
        save_path,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("symbol")
    parser.add_argument("interval")
    parser.add_argument("--history-limit", type=int, default=10000)
    args = parser.parse_args()
    train_and_evaluate(args.symbol, args.interval, history_limit=args.history_limit)


if __name__ == "__main__":
    main()
