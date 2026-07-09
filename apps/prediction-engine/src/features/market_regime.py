"""
Nhận diện CHẾ ĐỘ THỊ TRƯỜNG (market regime) từ lịch sử OHLCV, để prediction
làm giàu ngữ cảnh và (về sau) điều chỉnh hành vi theo từng tình huống.

Vấn đề: baseline EMA / LightGBM hiện dự đoán y hệt nhau bất kể thị trường
đang trending mạnh, đi ngang (sideways), hay biến động cực mạnh — trong khi
mỗi trạng thái này đòi hỏi mức tin cậy và cách diễn giải khác nhau (EMA trễ
khi breakout, nhiễu khi sideways). Module này phân loại trạng thái hiện tại
dựa trên chính các chỉ báo đã có (xem features/technical_indicators.py) và
trả về mô tả có cấu trúc + tóm tắt tiếng Việt cho người dùng.

Thuần tính toán (pure) — không đọc DB/Redis, dễ test độc lập. Tất cả ngưỡng
là giá trị KINH NGHIỆM (empirical) cho MVP, đặt thành hằng số có tên để tinh
chỉnh sau mà không phải dò trong code.
"""

from __future__ import annotations

from typing import Optional

import numpy as np
import pandas as pd

from features.technical_indicators import (
    bollinger_bands,
    relative_volume,
    rolling_volatility,
    rsi,
)

# Số nến tối thiểu để tính đủ chỉ báo (Bollinger period=20, RSI=14) + có chỗ
# ước lượng phân phối volatility. Ít hơn -> trả về regime "UNKNOWN" trung tính.
MIN_HISTORY_FOR_REGIME = 30

# Cửa sổ hồi quy tuyến tính để đo hướng + độ "sạch" của xu hướng gần đây.
TREND_WINDOW = 30

# --- Ngưỡng phân loại xu hướng ------------------------------------------
# drift = tổng % thay đổi giá (theo hồi quy) trên cả cửa sổ TREND_WINDOW.
# trend_strength = R^2 của hồi quy (0..1): càng gần 1, xu hướng càng thẳng/sạch.
STRONG_TREND_R2 = 0.6      # R^2 cao => giá đi gần như đường thẳng
STRONG_TREND_DRIFT = 0.02  # >= 2% drift trên cửa sổ => xu hướng đáng kể
TREND_R2 = 0.3
TREND_DRIFT = 0.008        # >= 0.8% drift => xu hướng nhẹ

# --- Ngưỡng volatility (theo percentile của chính nó gần đây) ------------
HIGH_VOL_PERCENTILE = 0.75  # vol hiện tại nằm trong top 25% gần đây => cao
LOW_VOL_PERCENTILE = 0.25   # nằm trong bottom 25% => thấp

# --- Ngưỡng Bollinger bandwidth cho squeeze/breakout --------------------
# Squeeze: bandwidth co lại rất hẹp so với gần đây (tích lũy trước biến động).
SQUEEZE_BANDWIDTH_PERCENTILE = 0.2
# Breakout: bandwidth đang nở ra + volume tăng đột biến.
BREAKOUT_VOLUME_RATIO = 1.8
BREAKOUT_BANDWIDTH_EXPANSION = 1.15  # bandwidth hiện tại / bandwidth trước đó

# --- Ngưỡng momentum (RSI) ----------------------------------------------
RSI_OVERBOUGHT = 70.0
RSI_OVERSOLD = 30.0

# --- Ngưỡng volume ------------------------------------------------------
HIGH_VOLUME_RATIO = 1.5
LOW_VOLUME_RATIO = 0.7

# Hệ số nhân confidence gợi ý theo từng regime (caller quyết định có dùng hay
# không, xem evaluation/calibration.py). Trending sạch => tin hơn; sideways/
# biến động/breakout => bớt tin vì khó dự đoán / dễ đảo chiều.
REGIME_CONFIDENCE_MODIFIER = {
    "STRONG_UPTREND": 1.10,
    "UPTREND": 1.05,
    "STRONG_DOWNTREND": 1.10,
    "DOWNTREND": 1.05,
    "RANGING": 0.95,
    "VOLATILE": 0.80,
    "SQUEEZE": 0.90,
    "BREAKOUT": 0.85,
    "UNKNOWN": 1.0,
}

_REGIME_SUMMARY_VI = {
    "STRONG_UPTREND": "Xu hướng TĂNG mạnh và rõ ràng.",
    "UPTREND": "Xu hướng tăng nhẹ.",
    "STRONG_DOWNTREND": "Xu hướng GIẢM mạnh và rõ ràng.",
    "DOWNTREND": "Xu hướng giảm nhẹ.",
    "RANGING": "Thị trường đi ngang (sideways), chưa có xu hướng rõ.",
    "VOLATILE": "Biến động mạnh, dao động thất thường, khó dự đoán.",
    "SQUEEZE": "Biên độ co hẹp (tích lũy) — thường trước một cú bứt phá.",
    "BREAKOUT": "Đang bứt phá kèm khối lượng tăng đột biến.",
    "UNKNOWN": "Chưa đủ dữ liệu để xác định trạng thái thị trường.",
}


def _to_ohlcv_frame(history: list[dict]) -> pd.DataFrame:
    df = pd.DataFrame(history).copy()
    for col in ("open", "high", "low", "close", "volume"):
        if col in df.columns:
            df[col] = df[col].astype(float)
    return df


def _linear_trend(closes: np.ndarray) -> tuple[float, float]:
    """
    Hồi quy tuyến tính giá close theo thời gian trên cửa sổ đã cho.

    Returns:
        (drift, r_squared):
            drift = tổng % thay đổi (theo đường hồi quy) trên cả cửa sổ,
                    dương = đi lên, âm = đi xuống.
            r_squared = độ "sạch" của xu hướng (0..1), càng cao càng thẳng.
    """
    n = len(closes)
    if n < 2:
        return 0.0, 0.0

    x = np.arange(n, dtype=float)
    slope, intercept = np.polyfit(x, closes, 1)

    fitted = slope * x + intercept
    ss_res = float(np.sum((closes - fitted) ** 2))
    ss_tot = float(np.sum((closes - closes.mean()) ** 2))
    r_squared = 1.0 - ss_res / ss_tot if ss_tot > 0 else 0.0

    mean_price = float(closes.mean())
    drift = (slope * (n - 1)) / mean_price if mean_price > 0 else 0.0

    return float(drift), float(max(0.0, min(1.0, r_squared)))


def _percentile_rank(series: pd.Series, value: float) -> float:
    """Vị trí phân vị (0..1) của `value` trong `series` (đã bỏ NaN)."""
    clean = series.dropna()
    if len(clean) == 0:
        return 0.5
    return float((clean <= value).mean())


def _classify(
    drift: float,
    trend_strength: float,
    vol_rank: float,
    bandwidth_rank: float,
    bandwidth_expansion: float,
    volume_ratio: float,
) -> str:
    """Cây quyết định phân loại regime từ các tín hiệu đã chuẩn hoá."""
    # Xu hướng MẠNH & sạch ưu tiên trước tiên: biên độ ổn định (bandwidth
    # rank thấp) trong một trend mượt KHÔNG phải là "squeeze tích lũy" — nếu
    # không kiểm tra trend trước, một downtrend/uptrend đều đặn sẽ bị bắt
    # nhầm thành SQUEEZE (bug đã gặp qua test).
    if trend_strength >= STRONG_TREND_R2 and abs(drift) >= STRONG_TREND_DRIFT:
        return "STRONG_UPTREND" if drift > 0 else "STRONG_DOWNTREND"

    # Breakout: biên độ đang nở ra + volume tăng đột biến (thường mở đầu trend).
    if (
        volume_ratio >= BREAKOUT_VOLUME_RATIO
        and bandwidth_expansion >= BREAKOUT_BANDWIDTH_EXPANSION
    ):
        return "BREAKOUT"

    # Squeeze: biên độ co rất hẹp so với gần đây (tích lũy), khi CHƯA có trend rõ.
    if bandwidth_rank <= SQUEEZE_BANDWIDTH_PERCENTILE:
        return "SQUEEZE"

    # Xu hướng nhẹ.
    if trend_strength >= TREND_R2 and abs(drift) >= TREND_DRIFT:
        return "UPTREND" if drift > 0 else "DOWNTREND"

    # Không có xu hướng rõ: phân biệt đi ngang yên ả vs biến động thất thường.
    if vol_rank >= HIGH_VOL_PERCENTILE:
        return "VOLATILE"
    return "RANGING"


def _momentum_state(rsi_value: Optional[float]) -> str:
    if rsi_value is None:
        return "neutral"
    if rsi_value >= RSI_OVERBOUGHT:
        return "overbought"
    if rsi_value <= RSI_OVERSOLD:
        return "oversold"
    return "neutral"


def _volume_state(volume_ratio: Optional[float]) -> str:
    if volume_ratio is None:
        return "normal"
    if volume_ratio >= HIGH_VOLUME_RATIO:
        return "high"
    if volume_ratio <= LOW_VOLUME_RATIO:
        return "low"
    return "normal"


def _volatility_level(vol_rank: float) -> str:
    if vol_rank >= HIGH_VOL_PERCENTILE:
        return "high"
    if vol_rank <= LOW_VOL_PERCENTILE:
        return "low"
    return "normal"


def _unknown_regime() -> dict:
    return {
        "regime": "UNKNOWN",
        "trend": "neutral",
        "trend_strength": 0.0,
        "drift_pct": 0.0,
        "volatility_level": "normal",
        "momentum": "neutral",
        "rsi": None,
        "volume_state": "normal",
        "confidence_modifier": 1.0,
        "summary": _REGIME_SUMMARY_VI["UNKNOWN"],
    }


def detect_regime(history: list[dict]) -> dict:
    """
    Phân loại trạng thái thị trường từ lịch sử nến đã đóng (OHLCV), sắp xếp
    thời gian tăng dần (cũ -> mới).

    Returns:
        dict: {
            "regime": str,               # nhãn chính (xem REGIME_CONFIDENCE_MODIFIER)
            "trend": "up"|"down"|"neutral",
            "trend_strength": float,     # 0..1 (R^2 của hồi quy giá)
            "drift_pct": float,          # tổng % thay đổi trên cửa sổ trend
            "volatility_level": "low"|"normal"|"high",
            "momentum": "overbought"|"oversold"|"neutral",
            "rsi": float | None,
            "volume_state": "high"|"normal"|"low",
            "confidence_modifier": float,  # gợi ý scale confidence theo regime
            "summary": str,              # mô tả tiếng Việt cho người dùng
        }

    Không raise khi thiếu dữ liệu — trả về regime "UNKNOWN" trung tính để
    caller (main.py) không bao giờ crash chỉ vì chưa đủ lịch sử.
    """
    if not history or len(history) < MIN_HISTORY_FOR_REGIME:
        return _unknown_regime()

    df = _to_ohlcv_frame(history)
    close = df["close"]

    # --- Xu hướng ---
    trend_closes = close.to_numpy()[-TREND_WINDOW:]
    drift, trend_strength = _linear_trend(trend_closes)
    if drift > 0:
        trend = "up"
    elif drift < 0:
        trend = "down"
    else:
        trend = "neutral"

    # --- Volatility (percentile so với chính nó gần đây) ---
    vol_series = rolling_volatility(close, period=14)
    current_vol = vol_series.iloc[-1]
    vol_rank = (
        _percentile_rank(vol_series, float(current_vol))
        if pd.notna(current_vol)
        else 0.5
    )

    # --- Bollinger bandwidth: squeeze / breakout ---
    bb = bollinger_bands(close, period=20, num_std=2.0)
    bandwidth = bb["bandwidth"]
    current_bw = bandwidth.iloc[-1]
    bandwidth_rank = (
        _percentile_rank(bandwidth, float(current_bw)) if pd.notna(current_bw) else 0.5
    )
    prev_bw = bandwidth.iloc[-2] if len(bandwidth) >= 2 else current_bw
    bandwidth_expansion = (
        float(current_bw) / float(prev_bw)
        if pd.notna(current_bw) and pd.notna(prev_bw) and float(prev_bw) > 0
        else 1.0
    )

    # --- Momentum (RSI) ---
    rsi_series = rsi(close, period=14)
    rsi_value = float(rsi_series.iloc[-1]) if pd.notna(rsi_series.iloc[-1]) else None

    # --- Volume ---
    volume_ratio = None
    if "volume" in df.columns:
        rvol_series = relative_volume(df["volume"], period=20)
        last_rvol = rvol_series.iloc[-1]
        volume_ratio = float(last_rvol) if pd.notna(last_rvol) else None

    regime = _classify(
        drift=drift,
        trend_strength=trend_strength,
        vol_rank=vol_rank,
        bandwidth_rank=bandwidth_rank,
        bandwidth_expansion=bandwidth_expansion,
        volume_ratio=volume_ratio if volume_ratio is not None else 1.0,
    )

    return {
        "regime": regime,
        "trend": trend,
        "trend_strength": round(trend_strength, 4),
        "drift_pct": round(drift * 100.0, 4),
        "volatility_level": _volatility_level(vol_rank),
        "momentum": _momentum_state(rsi_value),
        "rsi": round(rsi_value, 2) if rsi_value is not None else None,
        "volume_state": _volume_state(volume_ratio),
        "confidence_modifier": REGIME_CONFIDENCE_MODIFIER.get(regime, 1.0),
        "summary": _REGIME_SUMMARY_VI.get(regime, _REGIME_SUMMARY_VI["UNKNOWN"]),
    }
