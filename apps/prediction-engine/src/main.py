"""
Entrypoint cho prediction-engine (baseline + Genetic Algorithm self-learning).

Theo project_technical_spec.md muc 4.2 (pseudocode vong lap self-learning):

    Voi moi nen moi nhan duoc tu Redis channel `klines:<symbol>:<interval>`:
        - Neu isClosed == False: bo qua (baseline chi du doan khi co nen da
          dong, khong can realtime tick-by-tick).
        - Neu isClosed == True:
            (a) Neu co prediction truoc do voi target_time == openTime cua
                nen nay -> tinh accuracy (so sanh actual vs predicted) ->
                ghi DB (accuracy_log) + publish len Redis + luu vao
                accuracy_history in-memory.
            (b) Them nen vao buffer in-memory (history).
            (c) Moi OPTIMIZE_EVERY_N_EVALUATIONS lan danh gia: chay Genetic
                Algorithm (optimization/genetic.py) de tim ema_span/lookback
                tot hon, CHI ap dung neu ket qua generalize tren mot phan
                buffer rieng (validation) — neu khong, rollback/giu nguyen
                tham so hien tai (circuit breaker, spec muc 4.4). Tham so
                moi (neu duoc ap dung) duoc ghi vao model_params_history.
            (d) Tinh prediction moi cho nen ke tiep bang models/baseline.py
                (dung self.current_params) -> ghi DB (predictions) + publish
                len Redis.

Bien moi truong (doc qua python-dotenv):
    REDIS_URL     (default "redis://localhost:6379")
    DATABASE_URL  (bat buoc de ghi DB, khong co gia tri mac dinh an toan)

Danh sach symbol/interval can theo doi duoc phan giai boi
tracked_pairs.resolve_tracked_pairs() (uu tien: env TRACKED_PAIRS -> bang
tracked_pairs trong DB -> env SYMBOL/INTERVAL rieng le, mac dinh BTCUSDT/1m).
Moi cap chay tren 1 thread rieng, moi thread giu 1 PredictionEngine + 1
Redis pubsub connection doc lap (xem run()/_run_pair() ben duoi).
"""

from __future__ import annotations

import json
import logging
import os
import signal
import statistics
import sys
import threading
from collections import deque
from datetime import datetime, timedelta
from typing import Optional

from dotenv import load_dotenv

# Cho phep chay truc tiep `python src/main.py` (khong dung package-relative import).
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import ai_advisor  # noqa: E402
from db import (  # noqa: E402
    close_connection,
    get_recent_klines,
    get_tracked_pairs,
    insert_accuracy,
    insert_ai_signal,
    insert_model_params_history,
    insert_prediction,
)
from evaluation.accuracy import compute_accuracy  # noqa: E402
from evaluation.backtest import score_params  # noqa: E402
from evaluation.calibration import calibrate_confidence  # noqa: E402
from models import lightgbm_model  # noqa: E402
from models.baseline import (  # noqa: E402
    DEFAULT_EMA_SPAN,
    DEFAULT_LOOKBACK,
    MODEL_VERSION,
    predict_next_n_candles,
)
from optimization.genetic import optimize_params_with_validation  # noqa: E402
from redis_client import (  # noqa: E402
    get_redis_client,
    kline_channel,
    publish_accuracy,
    publish_prediction,
)
from tracked_pairs import resolve_tracked_pairs  # noqa: E402

load_dotenv()

logging.basicConfig(
    # .upper(): logging.basicConfig() chi chap nhan ten level VIET HOA
    # ("INFO", khong phai "info") — LOG_LEVEL trong .env.example dung chu
    # thuong, neu khong upper() truoc se raise ValueError ngay khi khoi dong.
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("prediction-engine")

# Kich thuoc toi da cua buffer in-memory chua cac nen da dong gan nhat.
CANDLE_BUFFER_MAXLEN = int(os.getenv("CANDLE_BUFFER_MAXLEN", "200"))

# Vong lap self-learning (spec muc 4.2): sau moi N nen duoc danh gia, thu
# toi uu lai ema_span/lookback bang Genetic Algorithm. So thap hon se toi uu
# thuong xuyen hon nhung tang chi phi CPU + rui ro "thrashing" (spec muc 4.4).
# Co the chinh qua bien moi truong ma khong can sua code/rebuild image.
OPTIMIZE_EVERY_N_EVALUATIONS = int(os.getenv("OPTIMIZE_EVERY_N_EVALUATIONS", "30"))
# Can it nhat bao nhieu nen trong buffer moi du de tach train/validation va
# chay walk-forward co y nghia (qua it se khong danh gia duoc gi).
MIN_HISTORY_FOR_OPTIMIZE = int(os.getenv("MIN_HISTORY_FOR_OPTIMIZE", "80"))
# Ti le chia buffer thanh train/validation noi bo cho GA (phan con lai la
# validation) — validation dung de rollback/circuit breaker (spec muc 4.4)
# neu tham so moi khong generalize (xem optimization/genetic.py).
TRAIN_SPLIT_RATIO = float(os.getenv("TRAIN_SPLIT_RATIO", "0.7"))
# So ket qua accuracy gan nhat duoc giu lai de tinh avg_accuracy khi ghi
# model_params_history (chi mang tinh thong ke/audit, khong dung de toi uu).
ACCURACY_HISTORY_MAXLEN = int(os.getenv("ACCURACY_HISTORY_MAXLEN", "200"))
# So nen tuong lai du doan moi chu ky (multi-step, xem models/baseline.py::
# predict_next_n_candles). CHI nen dau tien (t+1) duoc theo doi de tinh
# accuracy (self.pending_prediction) — cac nen con lai (t+2..t+N) chi de
# hien thi truc quan xu huong, sai so cua chung TICH LUY qua tung buoc nen
# khong dung de danh gia do chinh xac model.
PREDICTION_HORIZON = int(os.getenv("PREDICTION_HORIZON", "10"))

# Ensemble AI (DeepSeek, xem ai_advisor.py) — bat/tat + throttle bang
# ai_advisor.DEEPSEEK_ENABLED (mac dinh false, khong anh huong luong hien co).
# AI chi duoc goi moi N nen dong (khong phai moi nen) de gioi han chi phi/API
# rate limit + do tre network (~vai giay) tren thread cua tung cap — voi
# interval ngan (1m) NEN tang gia tri nay len (vd 10-15), voi interval dai
# (1h/1d) co the de 1 (goi moi nen). Chi ap dung cho buoc t+1 (buoc duoc theo
# doi accuracy), khong ap dung cho ca PREDICTION_HORIZON buoc (xem ai_advisor.py).
AI_REFRESH_EVERY_N_CANDLES = int(os.getenv("AI_REFRESH_EVERY_N_CANDLES", "3"))

if not (0.0 < TRAIN_SPLIT_RATIO < 1.0):
    raise ValueError(
        f"TRAIN_SPLIT_RATIO phai trong khoang (0, 1), nhan duoc: {TRAIN_SPLIT_RATIO}"
    )


def _parse_iso(ts: str) -> datetime:
    """Parse ISO timestamp string (nhu duoc publish tu ingestion-service)."""
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))


def _interval_to_timedelta(interval: str) -> timedelta:
    """
    Chuyen doi chuoi interval kieu Binance (vd '1m', '5m', '1h', '1d') sang
    timedelta, dung de tinh target_time (thoi diem nen ke tiep se dong).
    """
    # QUAN TRONG: "m" (thuong) = phut, "M" (hoa) = thang theo dung quy uoc
    # Binance — phai so sanh PHAN BIET HOA/THUONG, gop chung se lam target_time
    # cua khung thang bi tinh sai thanh +1 phut (bug thuc te da xay ra).
    unit = interval[-1]
    amount = int(interval[:-1])

    if unit == "M":
        # Thang khong co do dai co dinh (28-31 ngay) — dung xap xi 30 ngay/thang
        # chi de tinh target_time HIEN THI cho prediction; thoi diem nen thuc
        # su dong hay khong do truong "isClosed" tu Binance quyet dinh, khong
        # phu thuoc gia tri xap xi nay.
        return timedelta(days=30 * amount)
    if unit == "w":
        return timedelta(weeks=amount)
    if unit == "d":
        return timedelta(days=amount)
    if unit == "h":
        return timedelta(hours=amount)
    if unit == "m":
        return timedelta(minutes=amount)
    # Fallback an toan: mac dinh coi nhu phut.
    logger.warning("Khong nhan dien duoc don vi interval '%s', mac dinh dung phut.", interval)
    return timedelta(minutes=amount)


class PredictionEngine:
    """
    Giu buffer in-memory cac nen da dong + prediction dang cho danh gia,
    xu ly tung message kline nhan duoc tu Redis.
    """

    def __init__(self, symbol: str, interval: str) -> None:
        self.symbol = symbol
        self.interval = interval
        self.interval_delta = _interval_to_timedelta(interval)
        self.candle_buffer: deque[dict] = deque(maxlen=CANDLE_BUFFER_MAXLEN)
        # Prediction dang cho nen thuc te tuong ung dong lai de danh gia.
        # Key: ISO string cua target_time -> dict {id, predicted_close, predicted_open, ...}
        self.pending_prediction: Optional[dict] = None

        # Tham so baseline hien tai (co the duoc GA cap nhat qua thoi gian).
        self.current_params: dict = {
            "ema_span": DEFAULT_EMA_SPAN,
            "lookback": DEFAULT_LOOKBACK,
        }
        self.accuracy_history: deque[dict] = deque(maxlen=ACCURACY_HISTORY_MAXLEN)
        self.evaluations_since_optimize = 0
        # Throttle cho ensemble AI (xem AI_REFRESH_EVERY_N_CANDLES) — bat dau
        # tu gia tri lon de GOI NGAY lan dau tien co du lich su, khong phai
        # cho du AI_REFRESH_EVERY_N_CANDLES chu ky moi co tin hieu AI dau tien.
        self.candles_since_ai_call = AI_REFRESH_EVERY_N_CANDLES

        # Neu da co model LightGBM duoc train rieng cho (symbol, interval)
        # nay (xem training/train_lightgbm.py), dung no thay cho baseline EMA
        # trong _make_new_prediction. Chua train -> None -> tu dong fallback
        # ve baseline, KHONG BAO GIO crash vi thieu model (xem
        # models/lightgbm_model.py::load_model).
        self.ml_model = lightgbm_model.load_model(symbol, interval)
        if self.ml_model is not None:
            logger.info(
                "[%s:%s] Da nap model LightGBM (%s), se dung thay baseline EMA.",
                symbol,
                interval,
                lightgbm_model.MODEL_VERSION,
            )

    def seed_from_history(self, klines: list[dict]) -> None:
        """
        Nạp trước N nến đã đóng từ lịch sử (vd bảng `klines` trong DB, đã
        được ingestion-service bootstrap sẵn qua REST Binance) vào buffer và
        sinh NGAY 1 dự đoán đầu tiên — tránh phải đợi tới khi có nến THẬT
        đầu tiên đóng sau khi service khởi động (với khung giờ/ngày/tuần/
        tháng, có thể mất hàng giờ/ngày/tháng nếu không seed, xem _run_pair).

        Không đánh giá accuracy cho dự đoán này (không có pending_prediction
        từ trước đó để so sánh) — chỉ nhằm có ngay 1 dự đoán hiển thị cho
        người dùng, không phải 1 lần đánh giá độ chính xác model.
        """
        if not klines:
            return
        self.candle_buffer.extend(klines)
        self._make_new_prediction(klines[-1])

    def handle_message(self, raw_message: str) -> None:
        try:
            payload = json.loads(raw_message)
        except (TypeError, ValueError) as exc:
            logger.error("Bo qua message khong phai JSON hop le: %s", exc)
            return

        if payload.get("type") != "kline":
            return

        kline = payload.get("data")
        if not kline:
            logger.warning("Message kline thieu 'data', bo qua.")
            return

        if not kline.get("isClosed", False):
            # Baseline chi du doan khi co nen da dong, bo qua tick dang hinh thanh.
            return

        self._handle_closed_candle(kline)

    def _handle_closed_candle(self, kline: dict) -> None:
        open_time = kline.get("openTime")

        # (a) Neu co prediction truoc do khop voi nen vua dong -> tinh accuracy.
        # So sanh bang datetime da parse (thay vi so sanh chuoi truc tiep) de
        # tranh sai lech do khac dinh dang ISO (vd '+00:00' vs 'Z').
        if self.pending_prediction is not None and open_time and self._times_match(
            self.pending_prediction.get("target_time"), open_time
        ):
            self._evaluate_prediction(kline, self.pending_prediction)
            self.pending_prediction = None

        # (b) Them nen vao buffer.
        self.candle_buffer.append(kline)

        # (c) Tinh prediction moi cho nen ke tiep.
        self._make_new_prediction(kline)

    @staticmethod
    def _times_match(ts_a: Optional[str], ts_b: Optional[str]) -> bool:
        """So sanh 2 timestamp ISO string, bo qua khac biet dinh dang."""
        if not ts_a or not ts_b:
            return False
        try:
            return _parse_iso(ts_a) == _parse_iso(ts_b)
        except ValueError:
            return ts_a == ts_b

    def _evaluate_prediction(self, actual_kline: dict, prediction: dict) -> None:
        previous_close = None
        if len(self.candle_buffer) > 0:
            previous_close = float(self.candle_buffer[-1]["close"])

        try:
            result = compute_accuracy(
                actual=actual_kline,
                predicted=prediction,
                previous_close=previous_close,
            )
        except ValueError as exc:
            logger.error("Loi khi tinh accuracy: %s", exc)
            return

        accuracy_row = {
            "prediction_id": prediction.get("id"),
            "symbol": self.symbol,
            "interval": self.interval,
            "actual_close": float(actual_kline["close"]),
            "predicted_close": prediction["predicted_close"],
            "error_pct": result["error_pct"],
            "accuracy_pct": result["accuracy_pct"],
            # Thoi diem mo cua nen THAT vua duoc danh gia — frontend dung de
            # ve marker % chinh xac dung vi tri nen tren chart (xem
            # chartRenderer.js::setAccuracyMarkers).
            "open_time": actual_kline.get("openTime"),
        }

        insert_accuracy(accuracy_row)
        publish_accuracy(
            self.symbol,
            self.interval,
            {
                **accuracy_row,
                "direction_correct": result["direction_correct"],
            },
        )
        logger.info(
            "[%s:%s] Accuracy: error=%.4f%% accuracy=%.2f%% direction_correct=%s",
            self.symbol,
            self.interval,
            result["error_pct"],
            result["accuracy_pct"],
            result["direction_correct"],
        )

        self.accuracy_history.append(result)
        self._maybe_optimize_params()

    def _maybe_optimize_params(self) -> None:
        """
        Vong lap self-learning (spec muc 4.2): moi OPTIMIZE_EVERY_N_EVALUATIONS
        lan danh gia, thu toi uu lai ema_span/lookback bang Genetic Algorithm,
        CHI chap nhan tham so moi neu no generalize tren mot phan buffer chua
        tung duoc dung de toi uu (optimize_params_with_validation — rollback/
        circuit breaker theo muc 4.4 neu khong).
        """
        if self.ml_model is not None:
            # current_params (ema_span/lookback) khong duoc dung khi da co
            # model LightGBM (xem _make_new_prediction) -> toi uu GA cho
            # tham so nay vo nghia, bo qua de tiet kiem CPU (container gioi
            # han 1.0 CPU, xem infra/docker/docker-compose.yml).
            return

        self.evaluations_since_optimize += 1
        if self.evaluations_since_optimize < OPTIMIZE_EVERY_N_EVALUATIONS:
            return
        self.evaluations_since_optimize = 0

        history = list(self.candle_buffer)
        if len(history) < MIN_HISTORY_FOR_OPTIMIZE:
            logger.info(
                "[%s:%s] Bo qua optimize: chua du lich su (%d < %d nen).",
                self.symbol,
                self.interval,
                len(history),
                MIN_HISTORY_FOR_OPTIMIZE,
            )
            return

        split = int(len(history) * TRAIN_SPLIT_RATIO)
        train_slice = history[:split]
        validation_slice = history[split:]

        seed = [
            dict(self.current_params),
            {
                "ema_span": self.current_params["ema_span"],
                "lookback": max(10, self.current_params["lookback"] - 20),
            },
            {
                "ema_span": self.current_params["ema_span"],
                "lookback": self.current_params["lookback"] + 20,
            },
        ]

        try:
            new_params = optimize_params_with_validation(
                seed,
                train_fitness_fn=lambda p: score_params(train_slice, p),
                validation_fitness_fn=lambda p: score_params(validation_slice, p),
                population_size=10,
                generations=15,
            )
        except ValueError as exc:
            logger.error("[%s:%s] Loi khi chay Genetic Algorithm: %s", self.symbol, self.interval, exc)
            return

        if new_params == self.current_params:
            logger.info(
                "[%s:%s] Optimize: giu nguyen tham so hien tai %s (khong tim duoc gi tot hon tren validation).",
                self.symbol,
                self.interval,
                self.current_params,
            )
            return

        logger.info(
            "[%s:%s] Optimize: cap nhat tham so %s -> %s",
            self.symbol,
            self.interval,
            self.current_params,
            new_params,
        )
        self.current_params = new_params

        avg_accuracy = (
            statistics.mean(r["accuracy_pct"] for r in self.accuracy_history)
            if self.accuracy_history
            else None
        )
        insert_model_params_history(
            {
                "symbol": self.symbol,
                "params": new_params,
                "avg_accuracy": avg_accuracy,
            }
        )

    def _make_new_prediction(self, latest_kline: dict) -> None:
        history = list(self.candle_buffer)

        try:
            if self.ml_model is not None:
                predictions = lightgbm_model.predict_next_n_candles(
                    history,
                    self.ml_model,
                    n_steps=PREDICTION_HORIZON,
                )
                model_version = lightgbm_model.MODEL_VERSION
            else:
                predictions = predict_next_n_candles(
                    history,
                    ema_span=self.current_params["ema_span"],
                    lookback=self.current_params["lookback"],
                    n_steps=PREDICTION_HORIZON,
                )
                model_version = MODEL_VERSION
        except ValueError as exc:
            logger.error("Loi khi tinh prediction: %s", exc)
            return

        latest_open_time = _parse_iso(latest_kline["openTime"])
        current_close = float(latest_kline["close"])

        # Ensemble AI (DeepSeek) — CHI ap dung cho buoc t+1 (predictions[0]),
        # buoc duy nhat duoc theo doi de tinh accuracy (xem ghi chu
        # PREDICTION_HORIZON). Neu bi tat/loi/timeout, ai_signal = None va
        # predictions[0] giu nguyen y nhu truoc khi co tinh nang nay — khong
        # bao gio chan/thay doi luong du doan chinh vi 1 dich vu ben ngoai.
        ai_signal = None
        self.candles_since_ai_call += 1
        if ai_advisor.DEEPSEEK_ENABLED and self.candles_since_ai_call >= AI_REFRESH_EVERY_N_CANDLES:
            self.candles_since_ai_call = 0
            ai_signal = ai_advisor.get_ai_signal(self.symbol, self.interval, history, predictions[0])

        model_versions = [model_version] * len(predictions)
        if ai_signal is not None:
            predictions[0] = ai_advisor.blend_with_quant_signal(
                predictions[0], ai_signal, current_close=current_close
            )
            model_versions[0] = f"{model_version}+deepseek"

        pred_rows = []
        for step, prediction in enumerate(predictions):
            # Recalibrate confidence bang direction accuracy THUC TE gan day —
            # confidence goc tu model (hoac da ensemble voi AI o tren) chi
            # dua tren volatility/AI, khong tuong quan voi kha nang du doan
            # dung chieu thuc te (xem evaluation/calibration.py). Ap dung nhu
            # nhau cho moi buoc vi accuracy_history hien chi phan anh do
            # chinh xac cua rieng nen t+1 (xem ghi chu PREDICTION_HORIZON o tren).
            calibrated_confidence = calibrate_confidence(
                prediction["confidence"], self.accuracy_history
            )
            target_time = latest_open_time + self.interval_delta * (step + 1)

            pred_row = {
                "symbol": self.symbol,
                "interval": self.interval,
                "target_time": target_time.isoformat(),
                "predicted_open": prediction["predicted_open"],
                "predicted_high": prediction["predicted_high"],
                "predicted_low": prediction["predicted_low"],
                "predicted_close": prediction["predicted_close"],
                "confidence": calibrated_confidence,
                "model_version": model_versions[step],
            }
            pred_row["id"] = insert_prediction(pred_row)
            pred_rows.append(pred_row)

            if step == 0 and ai_signal is not None:
                # Audit trail rieng (bang ai_signals) de sau nay so sanh
                # accuracy_log cua cac prediction co/khong co AI (loc theo
                # model_version) — ghi loi o day KHONG duoc anh huong luong
                # du doan chinh (giong tinh than insert_accuracy/insert_prediction).
                insert_ai_signal(
                    {
                        "prediction_id": pred_row["id"],
                        "symbol": self.symbol,
                        "interval": self.interval,
                        "direction": prediction["ai_direction"],
                        "predicted_change_pct": prediction["ai_predicted_change_pct"],
                        "ai_confidence": prediction["ai_confidence"],
                        "blended": True,
                        "reasoning": prediction["ai_reasoning"],
                    }
                )

        # symbol/interval o day de frontend loc phong thu (giong het pattern
        # cua kline/accuracy_update) — du WS subscription da duoc gateway
        # scope dung theo (symbol, interval) roi, nhung giu nhat quan style
        # kiem tra giua 3 loai event.
        publish_prediction(
            self.symbol,
            self.interval,
            {"symbol": self.symbol, "interval": self.interval, "predictions": pred_rows},
        )
        logger.info(
            "[%s:%s] %d prediction moi, tu target_time=%s (predicted_close=%.6f) "
            "den target_time=%s (predicted_close=%.6f)",
            self.symbol,
            self.interval,
            len(pred_rows),
            pred_rows[0]["target_time"],
            pred_rows[0]["predicted_close"],
            pred_rows[-1]["target_time"],
            pred_rows[-1]["predicted_close"],
        )

        # Chi theo doi nen DAU TIEN (t+1) de doi danh gia khi nen tuong ung
        # dong — cac nen t+2..t+N khong duoc danh gia accuracy (xem ghi chu
        # PREDICTION_HORIZON). Viec so khop target_time voi openTime cua nen
        # ke tiep duoc thuc hien mem deo qua _times_match, khong phu thuoc
        # dinh dang chuoi ISO.
        first = pred_rows[0]
        self.pending_prediction = {
            "id": first["id"],
            "target_time": first["target_time"],
            "predicted_open": first["predicted_open"],
            "predicted_high": first["predicted_high"],
            "predicted_low": first["predicted_low"],
            "predicted_close": first["predicted_close"],
            "confidence": first["confidence"],
        }


def _run_pair(symbol: str, interval: str, stop_event: threading.Event) -> None:
    """
    Vong lap xu ly cho 1 cap symbol/interval, chay tren thread rieng. Dung
    pubsub.get_message(timeout=...) thay vi pubsub.listen() (blocking vo han)
    de co the kiem tra stop_event dinh ky va thoat sach khi nhan SIGTERM/SIGINT.
    """
    logger.info("Khoi dong prediction-engine (baseline) cho %s:%s", symbol, interval)

    engine = PredictionEngine(symbol=symbol, interval=interval)

    # Seed truoc buffer tu lich su da co san trong DB (ingestion-service da
    # bootstrap qua REST Binance) va sinh ngay 1 du doan khoi dong — tranh
    # nguoi dung phai doi toi khi co nen THAT dau tien dong sau khi service
    # khoi dong (voi 1h/1d/1w/1M co the mat hang gio/ngay/thang).
    try:
        recent_klines = get_recent_klines(symbol, interval, limit=CANDLE_BUFFER_MAXLEN)
        if recent_klines:
            engine.seed_from_history(recent_klines)
            logger.info(
                "[%s:%s] Da seed %d nen lich su va sinh du doan khoi dong.",
                symbol,
                interval,
                len(recent_klines),
            )
    except Exception:  # noqa: BLE001 - loi seed khong duoc chan mat thread, cho nen that
        logger.exception(
            "[%s:%s] Loi khi seed lich su khoi dong, se cho nen that dau tien dong.", symbol, interval
        )

    client = get_redis_client()
    pubsub = client.pubsub()

    channel = kline_channel(symbol, interval)
    pubsub.subscribe(channel)
    logger.info("Da subscribe channel Redis: %s", channel)

    try:
        while not stop_event.is_set():
            message = pubsub.get_message(timeout=1.0)
            if message is None or message.get("type") != "message":
                continue

            data = message.get("data")
            if data is None:
                continue

            engine.handle_message(data)
    except Exception:  # noqa: BLE001 - 1 cap loi khong duoc lam chet cac cap khac
        logger.exception("[%s:%s] Loi khong mong muon, thread dang thoat.", symbol, interval)
    finally:
        pubsub.close()
        logger.info("[%s:%s] Da thoat sach se.", symbol, interval)


def run() -> None:
    stop_event = threading.Event()

    def _handle_shutdown_signal(signum, _frame):
        signame = signal.Signals(signum).name
        logger.info("Nhan tin hieu %s, dang thoat...", signame)
        stop_event.set()

    signal.signal(signal.SIGTERM, _handle_shutdown_signal)
    signal.signal(signal.SIGINT, _handle_shutdown_signal)

    pairs = resolve_tracked_pairs(get_tracked_pairs_from_db=get_tracked_pairs)
    logger.info(
        "Khoi dong prediction-engine cho %d cap: %s",
        len(pairs),
        ", ".join(f"{pair['symbol']}/{pair['interval']}" for pair in pairs),
    )

    threads = [
        threading.Thread(
            target=_run_pair,
            args=(pair["symbol"], pair["interval"], stop_event),
            name=f"pair-{pair['symbol']}-{pair['interval']}",
            daemon=True,
        )
        for pair in pairs
    ]

    for thread in threads:
        thread.start()

    try:
        # Join voi timeout ngan de vong lap chinh van tinh tao, cho phep
        # signal handler o tren set stop_event roi thoat nhanh (khong phai
        # cho het timeout join moi lan kiem tra).
        while any(thread.is_alive() for thread in threads):
            for thread in threads:
                thread.join(timeout=0.5)
    except KeyboardInterrupt:
        stop_event.set()
    finally:
        stop_event.set()
        for thread in threads:
            thread.join(timeout=5)
        # Dong sau khi TAT CA thread da dung han — client Redis/DB connection
        # dung chung giua cac thread (xem get_redis_client()/get_connection()),
        # dong som se lam cac thread khac con dang chay bi loi.
        get_redis_client().close()
        close_connection()
        logger.info("Da thoat sach se.")


if __name__ == "__main__":
    run()
