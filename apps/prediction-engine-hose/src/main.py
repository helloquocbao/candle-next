"""
Entrypoint prediction-engine-hose — core dự đoán VÙNG GIÁ tương lai cho HOSE.

Vòng đời ĐỘC LẬP với prediction-engine (crypto). Mỗi chu kỳ:
  1. Với mỗi mã HOSE cấu hình (env HOSE_SYMBOLS), lấy OHLCV daily THẬT từ
     VNDIRECT (connectors/vndirect.py). Không có data -> BỎ QUA (không bịa).
  2. Upsert các nến vào bảng klines (market='hose').
  3. Tính N phiên giao dịch kế tiếp (calendar_hose) làm trục thời gian.
  4. Dựng dự đoán: NẾU đã có model LightGBM train riêng cho mã đó (xem
     training/train_lightgbm.py, file .txt trong HOSE_MODELS_DIR) -> dùng
     model đó (models/lightgbm_model.py). NGƯỢC LẠI (chưa train, hoặc file
     lỗi/không tương thích) -> tự động fallback về forecast_zone.py
     (heuristic drift EMA + ATR, không cần train trước) — KHÔNG bao giờ
     crash vì thiếu model.
  5. Ghi predictions (market='hose') vào DB.
Rồi ngủ REFRESH_INTERVAL_SEC và lặp lại (daily EOD nên tần suất thấp).

Biến môi trường:
  DATABASE_URL        (bắt buộc)
  HOSE_SYMBOLS        (mặc định "FPT,VNM,VIC,HPG,MWG,VCB" — mã HOSE thật)
  HOSE_N_STEPS        (mặc định 5)
  HOSE_HISTORY_DAYS   (mặc định 120 — số ngày lịch sử lấy về để tính feature)
  HOSE_MODELS_DIR     (mặc định /app/trained_models_hose — nơi tìm model
                        LightGBM đã train, xem models/lightgbm_model.py)
  REFRESH_INTERVAL_SEC(mặc định 3600)
"""

from __future__ import annotations

import logging
import os
import signal
import sys
import threading
import time as time_module
from datetime import datetime, timezone

from dotenv import load_dotenv

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import ai_advisor  # noqa: E402
from calendar_hose import next_n_trading_days  # noqa: E402
from connectors.vndirect import fetch_daily_ohlcv  # noqa: E402
from db import close_connection, insert_ai_signal, insert_prediction, upsert_kline  # noqa: E402
from forecast_zone import build_forecast_zone  # noqa: E402
from models import lightgbm_model  # noqa: E402

load_dotenv()

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("prediction-engine-hose")

INTERVAL = "1d"
DEFAULT_SYMBOLS = "FPT,VNM,VIC,HPG,MWG,VCB,PNJ"
N_STEPS = int(os.getenv("HOSE_N_STEPS", "5"))
HISTORY_DAYS = int(os.getenv("HOSE_HISTORY_DAYS", "120"))
REFRESH_INTERVAL_SEC = int(os.getenv("REFRESH_INTERVAL_SEC", "3600"))

# Cache model LightGBM đã nạp theo mã (tránh đọc lại file .txt mỗi chu kỳ
# EOD) — key: symbol, value: lgb.Booster đã nạp, hoặc None nếu mã đó chưa
# có model (đã kiểm tra 1 lần, không thử load lại mỗi chu kỳ để tránh I/O
# đĩa lặp lại vô ích khi biết chắc chưa train). Nạp lại khi service restart
# (đủ để nhận model MỚI train sau khi container được khởi động lại).
_ml_models: dict[str, object] = {}


def _get_ml_model(symbol: str):
    """Trả về model LightGBM đã cache cho `symbol`, tự nạp lần đầu gọi."""
    if symbol not in _ml_models:
        model = lightgbm_model.load_model(symbol, INTERVAL)
        _ml_models[symbol] = model
        if model is not None:
            logger.info(
                "[%s] Đã nạp model LightGBM (%s), sẽ dùng thay forecast_zone.py.",
                symbol,
                lightgbm_model.MODEL_VERSION,
            )
    return _ml_models[symbol]


def _parse_symbols() -> list[str]:
    raw = os.getenv("HOSE_SYMBOLS", DEFAULT_SYMBOLS)
    return [s.strip().upper() for s in raw.split(",") if s.strip()]


def _last_candle_date(history: list[dict]):
    """Ngày (date) của nến gần nhất, suy từ openTime ISO thật."""
    return datetime.fromisoformat(history[-1]["openTime"]).date()


def process_symbol(symbol: str) -> None:
    now = int(time_module.time())
    frm = now - HISTORY_DAYS * 24 * 3600

    history = fetch_daily_ohlcv(symbol, frm, now, interval=INTERVAL)
    if len(history) < 2:
        logger.warning("[%s] Không đủ dữ liệu thật (%d nến), bỏ qua.", symbol, len(history))
        return

    # Ghi nến thật vào DB.
    for kline in history:
        try:
            upsert_kline(kline)
        except Exception:  # noqa: BLE001
            logger.exception("[%s] Lỗi upsert kline %s", symbol, kline.get("openTime"))

    # Trục thời gian = N phiên giao dịch kế tiếp sau nến gần nhất.
    last_date = _last_candle_date(history)
    target_dates = next_n_trading_days(last_date, N_STEPS)

    # Dựng dự đoán: ưu tiên model LightGBM đã train riêng cho mã này (nếu
    # có), fallback forecast_zone.py (heuristic, luôn có sẵn) nếu chưa train
    # hoặc file model lỗi/không tương thích (xem lightgbm_model.load_model).
    ml_model = _get_ml_model(symbol)
    if ml_model is not None:
        try:
            step_predictions = lightgbm_model.predict_next_n_candles(history, ml_model, n_steps=N_STEPS)
        except ValueError as exc:
            logger.warning(
                "[%s] Lỗi khi dự đoán bằng LightGBM (%s) — fallback forecast_zone.py.", symbol, exc
            )
            ml_model = None

    if ml_model is None:
        try:
            zone = build_forecast_zone(history, n_steps=N_STEPS, target_dates=target_dates)
        except ValueError as exc:
            logger.error("[%s] Không dựng được vùng giá: %s", symbol, exc)
            return
    else:
        ref_close = float(history[-1]["close"])
        highs_pct, lows_pct = [], []
        predictions = []
        for step, prediction in enumerate(step_predictions, start=1):
            row = dict(prediction)
            row["step"] = step
            row["model_version"] = lightgbm_model.MODEL_VERSION
            row["target_time"] = target_dates[step - 1].isoformat()
            predictions.append(row)
            highs_pct.append((row["predicted_high"] / ref_close - 1.0) * 100.0)
            lows_pct.append((row["predicted_low"] / ref_close - 1.0) * 100.0)
        zone = {
            "ref_close": ref_close,
            "model_version": lightgbm_model.MODEL_VERSION,
            "predictions": predictions,
            "zone_upper_pct": max(highs_pct),
            "zone_lower_pct": min(lows_pct),
        }

    ref = zone["ref_close"]

    # Ensemble AI (DeepSeek) — CHỈ áp dụng cho phiên t+1 (predictions[0]).
    # Tần suất gọi ở đây (1 lần/mã/chu kỳ EOD, mặc định 3600s) đã đủ thấp,
    # không cần throttle thêm như bên prediction-engine (crypto, 1 nến/phút).
    # Nếu tắt/lỗi/timeout -> ai_signal=None -> zone["predictions"][0] giữ
    # nguyên như trước khi có tính năng này (xem ai_advisor.py).
    ai_signal = ai_advisor.get_ai_signal(symbol, history, zone["predictions"][0])
    if ai_signal is not None:
        blended = ai_advisor.blend_with_quant_signal(zone["predictions"][0], ai_signal, ref_close=ref)
        if blended["predicted_low"] > blended["predicted_high"]:
            blended["predicted_low"], blended["predicted_high"] = (
                blended["predicted_high"],
                blended["predicted_low"],
            )
        blended["model_version"] = f"{zone['predictions'][0]['model_version']}+deepseek"
        zone["predictions"][0] = blended

    count = 0
    for step_index, row in enumerate(zone["predictions"]):
        try:
            prediction_id = insert_prediction(
                {
                    "symbol": symbol,
                    "interval": INTERVAL,
                    "target_time": row["target_time"],
                    "predicted_open": row["predicted_open"],
                    "predicted_high": row["predicted_high"],
                    "predicted_low": row["predicted_low"],
                    "predicted_close": row["predicted_close"],
                    "confidence": row["confidence"],
                    "model_version": row["model_version"],
                }
            )
            count += 1

            if step_index == 0 and ai_signal is not None:
                # Audit trail riêng (bảng ai_signals) — lỗi ghi ở đây KHÔNG
                # được ảnh hưởng luồng ghi prediction chính.
                try:
                    insert_ai_signal(
                        {
                            "prediction_id": prediction_id,
                            "symbol": symbol,
                            "interval": INTERVAL,
                            "direction": row["ai_direction"],
                            "predicted_change_pct": row["ai_predicted_change_pct"],
                            "ai_confidence": row["ai_confidence"],
                            "blended": True,
                            "reasoning": row["ai_reasoning"],
                        }
                    )
                except Exception:  # noqa: BLE001
                    logger.exception("[%s] Lỗi ghi ai_signals cho bước 1", symbol)
        except Exception:  # noqa: BLE001
            logger.exception("[%s] Lỗi ghi prediction bước %s", symbol, row.get("step"))

    logger.info(
        "[%s] ref=%.2f | vùng dự đoán %d phiên: +%.2f%% / %.2f%% | đã ghi %d dự đoán.",
        symbol, ref, N_STEPS, zone["zone_upper_pct"], zone["zone_lower_pct"], count,
    )


def run_cycle(symbols: list[str]) -> None:
    for symbol in symbols:
        try:
            process_symbol(symbol)
        except Exception:  # noqa: BLE001 - 1 mã lỗi không làm chết cả chu kỳ
            logger.exception("[%s] Lỗi không mong muốn trong chu kỳ.", symbol)


def run() -> None:
    stop_event = threading.Event()

    def _shutdown(signum, _frame):
        logger.info("Nhận tín hiệu %s, đang thoát...", signal.Signals(signum).name)
        stop_event.set()

    signal.signal(signal.SIGTERM, _shutdown)
    signal.signal(signal.SIGINT, _shutdown)

    symbols = _parse_symbols()
    logger.info(
        "Khởi động prediction-engine-hose | %d mã: %s | N=%d phiên | refresh=%ds",
        len(symbols), ", ".join(symbols), N_STEPS, REFRESH_INTERVAL_SEC,
    )

    while not stop_event.is_set():
        started = datetime.now(timezone.utc)
        run_cycle(symbols)
        logger.info("Xong 1 chu kỳ lúc %s. Ngủ %ds.", started.isoformat(), REFRESH_INTERVAL_SEC)
        # Ngủ theo từng nhịp nhỏ để thoát nhanh khi nhận tín hiệu dừng.
        for _ in range(REFRESH_INTERVAL_SEC):
            if stop_event.is_set():
                break
            time_module.sleep(1)

    close_connection()
    logger.info("Đã thoát sạch sẽ.")


if __name__ == "__main__":
    run()
