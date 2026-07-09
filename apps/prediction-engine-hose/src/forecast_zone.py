"""
Builder VÙNG GIÁ DỰ ĐOÁN N phiên tới cho HOSE.

Tạo ra dải giá tương lai (hộp trên/dưới) từ lịch sử OHLCV THẬT:
  1. Đường kỳ vọng: dự đoán % thay đổi (drift) bằng EMA các return gần đây,
     nội suy nhiều bước (recursive) — giống tinh thần baseline crypto.
  2. Dải bất định: ± nửa biên độ trung bình (ATR đơn giản), NỞ DẦN theo bước.
  3. Kẹp mỗi bước vào phễu trần/sàn ±7% lũy tiến của HOSE (price_limit).
  4. Độ tin cậy giảm dần theo khoảng cách dự đoán.

Thuần (pure), KHÔNG mock/hardcode giá: mọi con số suy ra từ `history` thật
caller truyền vào. Nếu history quá ngắn -> raise ValueError (caller bỏ qua,
KHÔNG bịa dữ liệu).

Output mỗi bước KHỚP định dạng prediction của app crypto (predicted_open/
high/low/close, confidence, target_time) nên frontend vẽ vùng dùng lại 100%.
"""

from __future__ import annotations

from datetime import date
from typing import Optional

from price_limit import HOSE_DAILY_LIMIT, clamp, funnel_bounds, pct_change

DEFAULT_N_STEPS = 5
DEFAULT_LOOKBACK = 20
DEFAULT_EMA_SPAN = 10
# Nửa biên dải nở thêm mỗi bước xa hơn (bất định tăng theo horizon).
DEFAULT_BAND_WIDEN_PER_STEP = 0.5
# Độ tin cậy giảm ~15%/bước (giống crypto).
DEFAULT_CONFIDENCE_DECAY = 0.85
MODEL_VERSION = "hose-funnel-v1"


def _returns(closes: list[float]) -> list[float]:
    return [closes[i] / closes[i - 1] - 1.0 for i in range(1, len(closes)) if closes[i - 1] > 0]


def _ema_last(values: list[float], span: int) -> float:
    """EMA, trả về giá trị cuối. values rỗng -> 0.0."""
    if not values:
        return 0.0
    alpha = 2.0 / (span + 1.0)
    ema = values[0]
    for v in values[1:]:
        ema = alpha * v + (1.0 - alpha) * ema
    return ema


def _simple_atr(history: list[dict], lookback: int) -> float:
    """Trung bình (high - low) trên `lookback` nến gần nhất (biên độ TB)."""
    recent = history[-lookback:]
    ranges = [float(c["high"]) - float(c["low"]) for c in recent]
    return sum(ranges) / len(ranges) if ranges else 0.0


def _stability_confidence(closes: list[float]) -> float:
    """Confidence gốc (0..1): biến động càng thấp -> càng cao."""
    rets = _returns(closes)
    if len(rets) < 2:
        return 0.5
    mean = sum(rets) / len(rets)
    var = sum((r - mean) ** 2 for r in rets) / len(rets)
    vol = var ** 0.5
    return max(0.0, min(1.0, 1.0 / (1.0 + 50.0 * vol)))


def build_forecast_zone(
    history: list[dict],
    n_steps: int = DEFAULT_N_STEPS,
    lookback: int = DEFAULT_LOOKBACK,
    ema_span: int = DEFAULT_EMA_SPAN,
    limit: float = HOSE_DAILY_LIMIT,
    band_widen_per_step: float = DEFAULT_BAND_WIDEN_PER_STEP,
    confidence_decay: float = DEFAULT_CONFIDENCE_DECAY,
    target_dates: Optional[list[date]] = None,
) -> dict:
    """
    Dựng vùng giá dự đoán từ `history` (list nến đã đóng THẬT, tăng dần thời
    gian, mỗi nến có open/high/low/close).

    Args:
        history: lịch sử OHLCV thật (>= 2 nến).
        n_steps: số phiên dự đoán tới.
        target_dates: (tuỳ chọn) danh sách ngày giao dịch tương ứng từng bước
            (từ calendar_hose.next_n_trading_days). Nếu có, gắn vào target_time.

    Returns:
        dict {
          "ref_close": float,          # giá tham chiếu (đóng cửa gần nhất, THẬT)
          "model_version": str,
          "predictions": [ {step, target_time?, predicted_open, predicted_high,
                            predicted_low, predicted_close, floor, ceiling,
                            confidence}, ... ],
          "zone_upper_pct": float,     # % biên trên rộng nhất so với ref (nhãn hộp xanh)
          "zone_lower_pct": float,     # % biên dưới rộng nhất so với ref (nhãn hộp đỏ)
        }

    Raises:
        ValueError: nếu history < 2 nến hoặc n_steps < 1 (KHÔNG bịa dữ liệu).
    """
    if n_steps < 1:
        raise ValueError("build_forecast_zone: n_steps phải >= 1.")
    if len(history) < 2:
        raise ValueError("build_forecast_zone: cần >= 2 nến lịch sử thật.")
    if target_dates is not None and len(target_dates) != n_steps:
        raise ValueError("build_forecast_zone: target_dates phải cùng độ dài n_steps.")

    closes = [float(c["close"]) for c in history]
    ref_close = closes[-1]
    if ref_close <= 0:
        raise ValueError("build_forecast_zone: giá đóng cửa gần nhất không hợp lệ.")

    drift = _ema_last(_returns(closes[-(lookback + 1):]), ema_span)
    atr = _simple_atr(history, lookback)
    base_conf = _stability_confidence(closes[-(lookback + 1):])

    predictions = []
    running_close = ref_close   # giá tham chiếu lũy tiến qua từng bước
    highs_pct = []
    lows_pct = []

    for step in range(1, n_steps + 1):
        predicted_open = running_close
        predicted_close_raw = running_close * (1.0 + drift)

        half_range = (atr / 2.0) * (1.0 + band_widen_per_step * (step - 1))
        predicted_high_raw = max(predicted_open, predicted_close_raw) + half_range
        predicted_low_raw = min(predicted_open, predicted_close_raw) - half_range

        # Phễu trần/sàn tại bước này (so với ref_close gốc, lũy tiến).
        floor, ceiling = funnel_bounds(ref_close, step, limit)
        predicted_close = clamp(predicted_close_raw, floor, ceiling)
        predicted_high = clamp(predicted_high_raw, floor, ceiling)
        predicted_low = clamp(predicted_low_raw, floor, ceiling)
        if predicted_low > predicted_high:
            predicted_low, predicted_high = predicted_high, predicted_low

        confidence = base_conf * (confidence_decay ** (step - 1))

        row = {
            "step": step,
            "predicted_open": predicted_open,
            "predicted_high": predicted_high,
            "predicted_low": predicted_low,
            "predicted_close": predicted_close,
            "floor": floor,
            "ceiling": ceiling,
            "confidence": confidence,
            "model_version": MODEL_VERSION,
        }
        if target_dates is not None:
            row["target_time"] = target_dates[step - 1].isoformat()
        predictions.append(row)

        highs_pct.append(pct_change(predicted_high, ref_close))
        lows_pct.append(pct_change(predicted_low, ref_close))

        # Bước kế tiếp nội suy từ close dự đoán (recursive multi-step).
        running_close = predicted_close

    return {
        "ref_close": ref_close,
        "model_version": MODEL_VERSION,
        "predictions": predictions,
        "zone_upper_pct": max(highs_pct),
        "zone_lower_pct": min(lows_pct),
    }
