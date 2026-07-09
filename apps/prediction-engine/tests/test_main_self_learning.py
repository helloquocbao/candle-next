"""
Unit tests cho vong lap self-learning trong main.py (PredictionEngine):
GA duoc kich hoat sau N lan danh gia, chi ap dung tham so moi neu generalize
tren validation, va prediction ke tiep dung tham so hien tai (self.current_params).

Chạy: cd apps/prediction-engine && pytest

Tat ca I/O ben ngoai (DB, Redis) duoc monkeypatch — khong can Postgres/Redis
thuc de chay test nay.
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import main as main_module  # noqa: E402
from main import PredictionEngine  # noqa: E402


@pytest.fixture(autouse=True)
def _stub_io(monkeypatch):
    """Khong goi DB/Redis thuc trong unit test — chi ghi nhan cac loi goi."""
    calls = {"model_params_history": [], "accuracy": [], "prediction_inserts": [], "prediction_publishes": []}
    monkeypatch.setattr(
        main_module,
        "insert_accuracy",
        lambda row: calls["accuracy"].append(row) or 1,
    )
    monkeypatch.setattr(
        main_module,
        "insert_prediction",
        lambda row: calls["prediction_inserts"].append(row) or len(calls["prediction_inserts"]),
    )
    monkeypatch.setattr(main_module, "publish_accuracy", lambda *a, **k: None)
    monkeypatch.setattr(
        main_module,
        "publish_prediction",
        lambda symbol, interval, data: calls["prediction_publishes"].append(data),
    )

    monkeypatch.setattr(
        main_module,
        "insert_model_params_history",
        lambda row: calls["model_params_history"].append(row),
    )
    return calls


def make_kline(open_time_iso, close, is_closed=True):
    return {
        "openTime": open_time_iso,
        "open": close,
        "high": close + 1,
        "low": close - 1,
        "close": close,
        "isClosed": is_closed,
    }


def feed_candles(engine: PredictionEngine, closes: list[float]) -> None:
    """Gui tuan tu cac nen da dong qua handle_message (mo phong luong Redis)."""
    import json
    from datetime import datetime, timedelta

    base = datetime(2026, 1, 1)
    for i, close in enumerate(closes):
        open_time = (base + timedelta(minutes=i)).isoformat()
        kline = make_kline(open_time, close)
        payload = json.dumps({"type": "kline", "data": kline})
        engine.handle_message(payload)


def test_evaluate_prediction_includes_open_time_of_evaluated_candle(_stub_io):
    """
    accuracy_row ghi/publish phai kem open_time cua nen THAT vua duoc danh
    gia (khong phai target_time cua prediction) — frontend dung field nay de
    ve marker % chinh xac dung vi tri nen tren chart.
    """
    engine = PredictionEngine(symbol="BTCUSDT", interval="1m")
    feed_candles(engine, [100, 101, 102])

    assert len(_stub_io["accuracy"]) >= 1
    first_evaluated = _stub_io["accuracy"][0]
    # Nen thu 2 (index=1) la nen danh gia prediction sinh ra tu nen thu 1.
    assert first_evaluated["open_time"] == "2026-01-01T00:01:00"


def test_seed_from_history_populates_buffer_and_generates_prediction(_stub_io):
    """
    seed_from_history() phai nap toan bo klines lich su vao buffer VA sinh
    ngay 1 du doan (khong doi nen that dau tien dong) — day la fix cho van
    de: voi 1h/1d/1w/1M, candle_buffer rong hoan toan cho toi khi co nen
    that dau tien dong sau khi service khoi dong, co the mat hang gio/ngay/
    thang neu khong seed truoc tu lich su da co san trong DB.
    """
    engine = PredictionEngine(symbol="BTCUSDT", interval="1d")
    history = [make_kline(f"2026-01-0{i + 1}T00:00:00", 100 + i) for i in range(5)]

    engine.seed_from_history(history)

    assert len(engine.candle_buffer) == 5
    assert len(_stub_io["prediction_inserts"]) == main_module.PREDICTION_HORIZON
    assert len(_stub_io["prediction_publishes"]) == 1
    # Khong danh gia accuracy cho lan seed nay (chua co pending_prediction
    # tu truoc do de so sanh).
    assert _stub_io["accuracy"] == []


def test_seed_from_history_does_nothing_when_no_history(_stub_io):
    engine = PredictionEngine(symbol="BTCUSDT", interval="1d")

    engine.seed_from_history([])

    assert len(engine.candle_buffer) == 0
    assert _stub_io["prediction_inserts"] == []
    assert _stub_io["prediction_publishes"] == []


def test_make_new_prediction_generates_prediction_horizon_candles(_stub_io):
    """
    Moi lan 1 nen dong, engine phai sinh du PREDICTION_HORIZON du doan (mac
    dinh 10), ghi tung dong vao DB, nhung CHI publish 1 lan duy nhat len
    Redis voi field "predictions" la mang chua tat ca — khong publish rieng
    le tung nen (tranh spam WS message).
    """
    engine = PredictionEngine(symbol="BTCUSDT", interval="1m")
    feed_candles(engine, [100])  # 1 nen dong -> dung 1 chu ky _make_new_prediction

    assert len(_stub_io["prediction_inserts"]) == main_module.PREDICTION_HORIZON
    assert len(_stub_io["prediction_publishes"]) == 1

    published = _stub_io["prediction_publishes"][0]
    assert len(published["predictions"]) == main_module.PREDICTION_HORIZON


def test_make_new_prediction_only_tracks_first_step_for_accuracy(_stub_io):
    """pending_prediction (dung de tinh accuracy khi nen tiep theo dong) chi
    duoc gan bang nen DAU TIEN (t+1), khong phai nen xa nhat."""
    engine = PredictionEngine(symbol="BTCUSDT", interval="1m")
    feed_candles(engine, [100, 101])

    published = _stub_io["prediction_publishes"][-1]
    first_step = published["predictions"][0]

    assert engine.pending_prediction["target_time"] == first_step["target_time"]
    assert engine.pending_prediction["predicted_close"] == first_step["predicted_close"]


def test_make_new_prediction_target_times_increase_per_step(_stub_io):
    from datetime import datetime, timedelta

    engine = PredictionEngine(symbol="BTCUSDT", interval="1m")
    feed_candles(engine, [100, 101])

    published = _stub_io["prediction_publishes"][-1]["predictions"]
    times = [datetime.fromisoformat(p["target_time"]) for p in published]

    for prev, curr in zip(times, times[1:]):
        assert curr - prev == timedelta(minutes=1)


def test_engine_does_not_optimize_before_enough_evaluations(_stub_io):
    engine = PredictionEngine(symbol="BTCUSDT", interval="1m")
    initial_params = dict(engine.current_params)

    # It hon OPTIMIZE_EVERY_N_EVALUATIONS lan danh gia -> params khong doi.
    feed_candles(engine, [100 + (i % 5) for i in range(10)])

    assert engine.current_params == initial_params
    assert _stub_io["model_params_history"] == []


def test_engine_triggers_optimize_after_threshold_and_keeps_valid_params(_stub_io):
    engine = PredictionEngine(symbol="BTCUSDT", interval="1m")

    # Du nhieu nen de vuot OPTIMIZE_EVERY_N_EVALUATIONS va MIN_HISTORY_FOR_OPTIMIZE.
    closes = [100 + ((i * 3) % 11) for i in range(150)]
    feed_candles(engine, closes)

    # current_params phai luon la 1 dict hop le voi ema_span/lookback (du GA
    # giu nguyen hay cap nhat), khong bi hong/None.
    assert set(engine.current_params.keys()) == {"ema_span", "lookback"}
    assert engine.current_params["ema_span"] > 0
    assert engine.current_params["lookback"] > 0


def test_engine_prediction_uses_current_params(monkeypatch, _stub_io):
    engine = PredictionEngine(symbol="BTCUSDT", interval="1m")
    engine.current_params = {"ema_span": 7, "lookback": 33}

    captured = {}
    original_predict = main_module.predict_next_n_candles

    def spy_predict(history, ema_span=None, lookback=None, **kwargs):
        captured["ema_span"] = ema_span
        captured["lookback"] = lookback
        return original_predict(history, ema_span=ema_span, lookback=lookback, **kwargs)

    monkeypatch.setattr(main_module, "predict_next_n_candles", spy_predict)

    feed_candles(engine, [100, 101, 102])

    assert captured["ema_span"] == 7
    assert captured["lookback"] == 33
