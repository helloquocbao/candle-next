"""
Các chỉ báo kỹ thuật (technical indicators) dùng làm feature cho model ML
(xem models/lightgbm_model.py) — port nguyên vẹn từ prediction-engine
(crypto, apps/prediction-engine/src/features/technical_indicators.py),
module THUẦN pandas, không có gì đặc thù crypto nên không cần thích nghi.

Mỗi hàm nhận vào 1 pandas Series (cột close/volume) và trả về Series/DataFrame
CÙNG ĐỘ DÀI, các giá trị "warmup" (chưa đủ dữ liệu để tính) là NaN — caller
(feature_builder.py) chịu trách nhiệm drop NaN trước khi train/predict.
"""

from __future__ import annotations

import pandas as pd


def rsi(close: pd.Series, period: int = 14) -> pd.Series:
    """
    Relative Strength Index — dùng Wilder's smoothing (ewm alpha=1/period),
    đúng chuẩn RSI truyền thống thay vì simple moving average.
    """
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = gain.ewm(alpha=1.0 / period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1.0 / period, min_periods=period, adjust=False).mean()

    rs = avg_gain / avg_loss.replace(0, pd.NA)
    result = 100.0 - (100.0 / (1.0 + rs))
    # avg_loss == 0 (giá chỉ tăng, không giảm trong cả cửa sổ) -> RSI = 100.
    return result.fillna(100.0).where(avg_loss.notna())


def macd(close: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> pd.DataFrame:
    """
    MACD (Moving Average Convergence Divergence). Trả về DataFrame 3 cột:
    "macd" (đường MACD), "signal" (đường tín hiệu), "histogram" (macd - signal).
    """
    ema_fast = close.ewm(span=fast, adjust=False).mean()
    ema_slow = close.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    histogram = macd_line - signal_line

    return pd.DataFrame({"macd": macd_line, "signal": signal_line, "histogram": histogram})


def bollinger_bands(close: pd.Series, period: int = 20, num_std: float = 2.0) -> pd.DataFrame:
    """
    Bollinger Bands. Trả về DataFrame với "percent_b" (vị trí giá trong dải,
    0 = chạm biên dưới, 1 = chạm biên trên) và "bandwidth" (độ rộng dải,
    chuẩn hoá theo trung bình) — 2 feature này thường hữu ích hơn bản thân
    upper/lower tuyệt đối (không phụ thuộc thang giá của từng mã).
    """
    middle = close.rolling(period).mean()
    std = close.rolling(period).std()
    upper = middle + num_std * std
    lower = middle - num_std * std

    percent_b = (close - lower) / (upper - lower)
    bandwidth = (upper - lower) / middle

    return pd.DataFrame({"percent_b": percent_b, "bandwidth": bandwidth})


def relative_volume(volume: pd.Series, period: int = 20) -> pd.Series:
    """Volume hiện tại / trung bình volume `period` phiên gần nhất."""
    vol_ma = volume.rolling(period).mean()
    return volume / vol_ma.replace(0, pd.NA)


def rolling_volatility(close: pd.Series, period: int = 14) -> pd.Series:
    """Độ lệch chuẩn của % thay đổi giá — ước lượng biến động gần đây."""
    return close.pct_change().rolling(period).std()
