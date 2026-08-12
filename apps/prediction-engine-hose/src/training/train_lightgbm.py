"""
Train model LightGBM dự đoán % thay đổi giá (return) của phiên kế tiếp, cho
1 mã HOSE cụ thể (daily bar) — port từ prediction-engine (crypto,
training/train_lightgbm.py), thích nghi:

  - Nguồn dữ liệu: lấy TRỰC TIẾP qua vnstock (connectors/vndirect.py::
    fetch_daily_ohlcv), tối đa ~8 năm lịch sử (giới hạn bản community của
    vnstock) — KHÔNG phụ thuộc bảng `klines` trong DB đã backfill được bao
    nhiêu (khác crypto, đã có training/backfill_history.py riêng để nạp DB
    trước khi train). Có thể dùng --from-db để đọc từ DB thay thế nếu muốn.

  - Baseline so sánh: forecast_zone.build_forecast_zone (drift EMA + ATR,
    hiện đang chạy live trong main.py) — CHỈ lấy predictions[0] (bước t+1)
    để so sánh single-step công bằng với LightGBM (khác models.baseline EMA
    của crypto, nhưng cùng vai trò "baseline heuristic đang chạy production").

Đánh giá trên tập validation (time-based split, KHÔNG random — tránh
lookahead bias) và so sánh trung thực với 2 mức đối chiếu, TÁCH RIÊNG 2 loại
chỉ số (không trộn lẫn):

  - MAPE (sai số giá): so với "naive" (dự đoán không đổi) VÀ forecast_zone
    — cả 2 đều là mức so sánh hợp lệ cho MAPE vì cả 2 có giá trị dự đoán cụ
    thể để tính sai số.

  - Direction accuracy: CHỈ so với forecast_zone và mức 50% (tung xu ngẫu
    nhiên), KHÔNG so với naive — vì naive luôn dự đoán "không đổi"
    (predicted_direction = 0), mà evaluation/accuracy.py::compute_accuracy so
    sánh CHIỀU theo DẤU (sign), nên naive gần như LUÔN bị tính "sai chiều"
    (giá thực tế gần như không bao giờ đứng yên tuyệt đối) — đây là hành vi
    ĐÚNG của hàm so sánh, nhưng đồng nghĩa "naive direction accuracy" là 1
    con số VÔ NGHĨA để làm mốc so sánh.

Tiêu chí triển khai (giống tinh thần crypto): model được lưu NẾU vượt qua cả
naive VÀ forecast_zone về MAPE, và KHÔNG tệ hơn forecast_zone quá
DIRECTION_REGRESSION_TOLERANCE_PP điểm % về direction accuracy.

Với daily bar HOSE (ít dữ liệu hơn crypto 1m rất nhiều — vài trăm đến ~2000
phiên/mã so với hàng chục nghìn nến), cần history_limit đủ lớn (mặc định lấy
hết ~8 năm) để có đủ dữ liệu train + validation có ý nghĩa sau khi trừ
warmup (MIN_HISTORY_FOR_FEATURES=40, xem feature_builder.py).

Chạy thủ công (không nằm trong vòng lặp chính của service):
    cd apps/prediction-engine-hose/src
    python -m training.train_lightgbm FPT
    python -m training.train_lightgbm FPT --history-days 2000
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
import time as time_module

import lightgbm as lgb
import numpy as np

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from connectors.vndirect import fetch_daily_ohlcv  # noqa: E402
from evaluation.accuracy import compute_accuracy  # noqa: E402
from features.feature_builder import FEATURE_COLUMNS, build_training_frame  # noqa: E402
from forecast_zone import build_forecast_zone  # noqa: E402
from models import lightgbm_model  # noqa: E402

logging.basicConfig(level="INFO", format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("train_lightgbm_hose")

INTERVAL = "1d"
VALIDATION_FRACTION = 0.2
# Direction accuracy ở daily bar có thể dao động quanh 50% (giống crypto 1m)
# — chênh lệch nhỏ vài điểm % là NHIỀU THỐNG KÊ, không phải model tệ hơn
# thật sự. Cho phép LightGBM kém hơn forecast_zone tối đa bao nhiêu điểm %
# về direction mà VẪN được chấp nhận triển khai, MIỄN LÀ thắng rõ về MAPE.
DIRECTION_REGRESSION_TOLERANCE_PP = 2.0
# Mặc định lấy tối đa lịch sử vnstock cho phép (~8 năm bản community) — daily
# bar nên cần NHIỀU lịch sử hơn crypto 1m tính theo SỐ PHIÊN (dù ít hơn theo
# số nến tuyệt đối) để có đủ mẫu train/validation có ý nghĩa.
DEFAULT_HISTORY_DAYS = 8 * 365
# Tối thiểu bao nhiêu phiên mới train có ý nghĩa (dư ra sau MIN_HISTORY_FOR_
# FEATURES=40 để còn mẫu train+validation thật) — thấp hơn ngưỡng này thì từ
# chối train luôn, tránh model học trên vài chục mẫu vô nghĩa.
MIN_KLINES_FOR_TRAINING = 120
LGBM_PARAMS = {
    "objective": "regression",
    "metric": "mae",
    "learning_rate": 0.05,
    "num_leaves": 15,
    "min_data_in_leaf": 20,
    "verbose": -1,
}


def _forecast_zone_predict_next(klines: list[dict]) -> dict:
    """
    Baseline heuristic đang chạy production (forecast_zone.py) — chỉ lấy
    bước t+1 (predictions[0]) để so sánh single-step công bằng với LightGBM.
    n_steps=1 vì chỉ cần bước gần nhất, không cần dựng cả vùng giá N phiên.
    """
    zone = build_forecast_zone(klines, n_steps=1)
    return zone["predictions"][0]


def _evaluate_on_validation(klines: list[dict], val_frame, predicted_returns) -> dict:
    """
    So sánh LightGBM vs naive vs forecast_zone TRÊN CÙNG 1 tập validation.

    `val_frame.index` là vị trí THẬT trong `klines` gốc (pandas giữ nguyên
    index gốc qua .dropna(), xem features/feature_builder.py) — dùng trực
    tiếp để cắt lịch sử dùng cho forecast_zone tại TỪNG thời điểm trong
    validation set, không bị lệch do warmup/NaN đã bị drop.
    """
    lgbm_errors, naive_errors, fz_errors = [], [], []
    lgbm_hits, naive_hits, fz_hits = 0, 0, 0

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
            fz_pred = _forecast_zone_predict_next(klines[: klines_idx + 1])
            fz_result = compute_accuracy(actual, fz_pred, previous_close=current_close)
            fz_errors.append(fz_result["error_pct"])
            fz_hits += int(fz_result["direction_correct"])
        except ValueError:
            continue  # chưa đủ lịch sử cho forecast_zone ở những điểm rất đầu chuỗi

    n = len(val_frame)
    return {
        "n": n,
        "lgbm": {"direction_pct": 100 * lgbm_hits / n, "mape": float(np.mean(lgbm_errors))},
        "naive": {"direction_pct": 100 * naive_hits / n, "mape": float(np.mean(naive_errors))},
        "forecast_zone": {
            "direction_pct": 100 * fz_hits / len(fz_errors) if fz_errors else None,
            "mape": float(np.mean(fz_errors)) if fz_errors else None,
        },
    }


def should_deploy(report: dict) -> tuple[bool, float]:
    """
    Quyết định model có đạt tiêu chí triển khai hay không (xem docstring đầu
    file về lý do tách riêng MAPE/direction). Tách thành hàm thuần (không
    gọi I/O) để test được mà không cần train thật.

    Returns:
        (deploy: bool, direction_regression_pp: float) — direction_regression_pp
        dương nghĩa LightGBM kém hơn forecast_zone bao nhiêu điểm %, âm nghĩa tốt hơn.
    """
    beats_naive_mape = report["lgbm"]["mape"] <= report["naive"]["mape"]
    beats_fz_mape = (
        report["forecast_zone"]["mape"] is None or report["lgbm"]["mape"] <= report["forecast_zone"]["mape"]
    )
    direction_regression_pp = (
        0.0
        if report["forecast_zone"]["direction_pct"] is None
        else report["forecast_zone"]["direction_pct"] - report["lgbm"]["direction_pct"]
    )
    direction_acceptable = direction_regression_pp <= DIRECTION_REGRESSION_TOLERANCE_PP

    deploy = beats_naive_mape and beats_fz_mape and direction_acceptable
    return deploy, direction_regression_pp


def train_and_evaluate(symbol: str, history_days: int = DEFAULT_HISTORY_DAYS) -> None:
    symbol = symbol.upper()
    now = int(time_module.time())
    frm = now - history_days * 24 * 3600

    klines = fetch_daily_ohlcv(symbol, frm, now, interval=INTERVAL)
    if len(klines) < MIN_KLINES_FOR_TRAINING:
        logger.error(
            "[%s] Chỉ có %d phiên lịch sử — quá ít để train có ý nghĩa (cần >= %d). "
            "Kiểm tra lại mã hoặc tăng --history-days.",
            symbol,
            len(klines),
            MIN_KLINES_FOR_TRAINING,
        )
        return
    logger.info("[%s] Đã tải %d phiên lịch sử (daily, %d năm)", symbol, len(klines), history_days // 365)

    frame = build_training_frame(klines)
    logger.info("[%s] Ma trận feature: %d dòng (sau khi bỏ warmup/NaN)", symbol, len(frame))

    split_idx = int(len(frame) * (1 - VALIDATION_FRACTION))
    train_frame = frame.iloc[:split_idx]
    val_frame = frame.iloc[split_idx:]

    if len(train_frame) < 30 or len(val_frame) < 10:
        logger.error(
            "[%s] Sau khi chia train/validation còn quá ít mẫu (train=%d, val=%d) — "
            "cần thêm lịch sử (--history-days lớn hơn).",
            symbol,
            len(train_frame),
            len(val_frame),
        )
        return

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

    logger.info("=== [%s] Kết quả trên tập validation (%d mẫu) ===", symbol, report["n"])
    logger.info(
        "LightGBM      : direction accuracy=%.2f%%  MAPE=%.4f%%",
        report["lgbm"]["direction_pct"],
        report["lgbm"]["mape"],
    )
    logger.info(
        "Naive         : MAPE=%.4f%%  (direction accuracy KHÔNG tính — xem docstring đầu file)",
        report["naive"]["mape"],
    )
    if report["forecast_zone"]["direction_pct"] is not None:
        logger.info(
            "forecast_zone : direction accuracy=%.2f%%  MAPE=%.4f%%",
            report["forecast_zone"]["direction_pct"],
            report["forecast_zone"]["mape"],
        )
    logger.info("(Tung xu ngẫu nhiên = 50%% direction accuracy — mốc tham chiếu tuyệt đối)")

    deploy, direction_regression_pp = should_deploy(report)

    if not deploy:
        logger.warning(
            "[%s] LightGBM KHÔNG đạt tiêu chí triển khai (MAPE phải <= naive và forecast_zone, "
            "direction không được kém forecast_zone quá %.1f điểm %%) — KHÔNG lưu model này. "
            "Cần thêm feature/dữ liệu/tuning trước khi thử lại.",
            symbol,
            DIRECTION_REGRESSION_TOLERANCE_PP,
        )
        return

    os.makedirs(lightgbm_model.MODELS_DIR, exist_ok=True)
    save_path = lightgbm_model.model_path(symbol, INTERVAL)
    booster.save_model(save_path)
    logger.info(
        "[%s] Model đạt tiêu chí triển khai (MAPE tốt hơn naive+forecast_zone, direction lệch "
        "%.2f điểm %% trong ngưỡng cho phép %.1f) — đã lưu vào %s",
        symbol,
        direction_regression_pp,
        DIRECTION_REGRESSION_TOLERANCE_PP,
        save_path,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("symbol", help="Mã HOSE, vd FPT")
    parser.add_argument(
        "--history-days",
        type=int,
        default=DEFAULT_HISTORY_DAYS,
        help=f"Số ngày lịch sử lấy về qua vnstock (mặc định {DEFAULT_HISTORY_DAYS}, ~8 năm).",
    )
    args = parser.parse_args()
    train_and_evaluate(args.symbol, history_days=args.history_days)


if __name__ == "__main__":
    main()
