"""
Cac chi bao ky thuat (technical indicators) dung lam feature cho model ML
(xem models/lightgbm_model.py) — cong thuc chuan, tinh bang pandas rolling/
ewm thay vi vong lap tay (khac voi models/baseline.py::_ema/_simple_atr vi o
day can nhieu chi bao phuc tap hon, pandas giup code ngan va dung hon nhieu).

Moi ham nhan vao 1 pandas Series (cot close/volume) va tra ve Series/DataFrame
CUNG DO DAI, cac gia tri "warmup" (chua du du lieu de tinh) la NaN — caller
(feature_builder.py) chiu trach nhiem drop NaN truoc khi train/predict.
"""

from __future__ import annotations

import pandas as pd


def rsi(close: pd.Series, period: int = 14) -> pd.Series:
    """
    Relative Strength Index — dung Wilder's smoothing (ewm alpha=1/period),
    dung chuan RSI truyen thong thay vi simple moving average.
    """
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = gain.ewm(alpha=1.0 / period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1.0 / period, min_periods=period, adjust=False).mean()

    rs = avg_gain / avg_loss.replace(0, pd.NA)
    result = 100.0 - (100.0 / (1.0 + rs))
    # avg_loss == 0 (gia chi tang, khong giam trong ca cua so) -> RSI = 100.
    return result.fillna(100.0).where(avg_loss.notna())


def macd(close: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> pd.DataFrame:
    """
    MACD (Moving Average Convergence Divergence). Tra ve DataFrame 3 cot:
    "macd" (duong MACD), "signal" (duong tin hieu), "histogram" (macd - signal).
    """
    ema_fast = close.ewm(span=fast, adjust=False).mean()
    ema_slow = close.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    histogram = macd_line - signal_line

    return pd.DataFrame({"macd": macd_line, "signal": signal_line, "histogram": histogram})


def bollinger_bands(close: pd.Series, period: int = 20, num_std: float = 2.0) -> pd.DataFrame:
    """
    Bollinger Bands. Tra ve DataFrame voi "percent_b" (vi tri gia trong dai,
    0 = cham bien duoi, 1 = cham bien tren) va "bandwidth" (do rong dai,
    chuan hoa theo trung binh) — 2 feature nay thuong huu ich hon ban than
    upper/lower tuyet doi (khong phu thuoc thang gia cua tung coin).
    """
    middle = close.rolling(period).mean()
    std = close.rolling(period).std()
    upper = middle + num_std * std
    lower = middle - num_std * std

    percent_b = (close - lower) / (upper - lower)
    bandwidth = (upper - lower) / middle

    return pd.DataFrame({"percent_b": percent_b, "bandwidth": bandwidth})


def relative_volume(volume: pd.Series, period: int = 20) -> pd.Series:
    """Volume hien tai / trung binh volume `period` nen gan nhat."""
    vol_ma = volume.rolling(period).mean()
    return volume / vol_ma.replace(0, pd.NA)


def rolling_volatility(close: pd.Series, period: int = 14) -> pd.Series:
    """Do lech chuan cua % thay doi gia — uoc luong bien dong gan day."""
    return close.pct_change().rolling(period).std()
