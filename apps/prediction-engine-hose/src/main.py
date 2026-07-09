"""
Entrypoint prediction-engine-hose — core dự đoán VÙNG GIÁ tương lai cho HOSE.

Vòng đời ĐỘC LẬP với prediction-engine (crypto). Mỗi chu kỳ:
  1. Với mỗi mã HOSE cấu hình (env HOSE_SYMBOLS), lấy OHLCV daily THẬT từ
     VNDIRECT (connectors/vndirect.py). Không có data -> BỎ QUA (không bịa).
  2. Upsert các nến vào bảng klines (market='hose').
  3. Tính N phiên giao dịch kế tiếp (calendar_hose) làm trục thời gian.
  4. Dựng vùng giá dự đoán (forecast_zone) — kẹp trong phễu trần/sàn ±7%.
  5. Ghi predictions (market='hose') vào DB.
Rồi ngủ REFRESH_INTERVAL_SEC và lặp lại (daily EOD nên tần suất thấp).

Biến môi trường:
  DATABASE_URL        (bắt buộc)
  HOSE_SYMBOLS        (mặc định "FPT,VNM,VIC,HPG,MWG,VCB" — mã HOSE thật)
  HOSE_N_STEPS        (mặc định 5)
  HOSE_HISTORY_DAYS   (mặc định 120 — số ngày lịch sử lấy về để tính feature)
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

from calendar_hose import next_n_trading_days  # noqa: E402
from connectors.vndirect import fetch_daily_ohlcv  # noqa: E402
from db import close_connection, insert_prediction, upsert_kline  # noqa: E402
from forecast_zone import build_forecast_zone  # noqa: E402

load_dotenv()

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("prediction-engine-hose")

INTERVAL = "1d"
DEFAULT_SYMBOLS = "FPT,VNM,VIC,HPG,MWG,VCB"
N_STEPS = int(os.getenv("HOSE_N_STEPS", "5"))
HISTORY_DAYS = int(os.getenv("HOSE_HISTORY_DAYS", "120"))
REFRESH_INTERVAL_SEC = int(os.getenv("REFRESH_INTERVAL_SEC", "3600"))


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

    # Dựng vùng giá (chỉ từ history thật).
    try:
        zone = build_forecast_zone(history, n_steps=N_STEPS, target_dates=target_dates)
    except ValueError as exc:
        logger.error("[%s] Không dựng được vùng giá: %s", symbol, exc)
        return

    ref = zone["ref_close"]
    count = 0
    for row in zone["predictions"]:
        try:
            insert_prediction(
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
