"""
Xay dung ma tran feature (cho training) va vector feature cho 1 thoi diem
(cho inference/predict truc tiep) tu lich su OHLCV — dung CHUNG 1 danh sach
FEATURE_COLUMNS cho ca 2 truong hop de tranh train/serve skew (feature luc
train va luc predict PHAI giong het nhau, khac thu tu/thieu cot se lam model
du doan sai ma khong bao loi ro rang).
"""

from __future__ import annotations

import pandas as pd

from features.technical_indicators import (
    bollinger_bands,
    macd,
    relative_volume,
    rolling_volatility,
    rsi,
)

RETURN_LAG_PERIODS = (1, 3, 5, 10)

FEATURE_COLUMNS = [
    "rsi_14",
    "macd",
    "macd_signal",
    "macd_hist",
    "bb_percent_b",
    "bb_bandwidth",
    "relative_volume_20",
    "volatility_14",
    "ema_10_ratio",
    *[f"return_{p}" for p in RETURN_LAG_PERIODS],
]

# So nen "khoi dong" toi thieu truoc khi feature dau tien het NaN (chi bao
# dai nhat la MACD slow=26+signal=9 ~ 35, Bollinger/volume period=20 — lay
# du phong 40 de chac chan an toan).
MIN_HISTORY_FOR_FEATURES = 40


def _compute_all_features(df: pd.DataFrame) -> pd.DataFrame:
    """Tinh toan va gan toan bo cot feature vao df (KHONG drop NaN o day)."""
    close = df["close"]
    volume = df["volume"]

    df["rsi_14"] = rsi(close, 14)

    macd_df = macd(close)
    df["macd"] = macd_df["macd"]
    df["macd_signal"] = macd_df["signal"]
    df["macd_hist"] = macd_df["histogram"]

    bb_df = bollinger_bands(close)
    df["bb_percent_b"] = bb_df["percent_b"]
    df["bb_bandwidth"] = bb_df["bandwidth"]

    df["relative_volume_20"] = relative_volume(volume, 20)
    df["volatility_14"] = rolling_volatility(close, 14)

    ema_10 = close.ewm(span=10, adjust=False).mean()
    df["ema_10_ratio"] = close / ema_10 - 1.0

    for p in RETURN_LAG_PERIODS:
        df[f"return_{p}"] = close.pct_change(p)

    return df


def _next_period_return(close: pd.Series) -> pd.Series:
    """% thay doi gia close cua nen KE TIEP so voi nen hien tai (shift -1)."""
    return close.pct_change().shift(-1)


def _to_float_ohlcv(klines: list[dict]) -> pd.DataFrame:
    df = pd.DataFrame(klines).copy()
    for col in ("open", "high", "low", "close", "volume"):
        df[col] = df[col].astype(float)
    return df


def build_training_frame(klines: list[dict]) -> pd.DataFrame:
    """
    klines: danh sach dict co open/high/low/close/volume, SAP XEP THOI GIAN
    TANG DAN (cu -> moi).

    Tra ve DataFrame voi cac cot FEATURE_COLUMNS + "target_return" (% thay
    doi gia close cua NEN KE TIEP — bien muc tieu can du doan) + "close" (de
    quy doi target_return nguoc lai thanh gia tuyet doi khi can) — da drop
    het cac dong NaN (warmup dau chuoi va dong cuoi cung khong co nen ke
    tiep de lam target).
    """
    df = _to_float_ohlcv(klines)
    df = _compute_all_features(df)
    # Du doan % THAY DOI GIA (return) thay vi gia tuyet doi — de model hoc
    # duoc pattern chung, khong phai hoc lai thang gia rieng cua tung coin
    # (BTC ~60000 vs SOL ~77), giup 1 kien truc feature dung chung duoc.
    df["target_return"] = _next_period_return(df["close"])

    return df[[*FEATURE_COLUMNS, "target_return", "close"]].dropna()


def build_inference_features(klines: list[dict]) -> pd.DataFrame | None:
    """
    Tinh feature cho DONG CUOI CUNG (thoi diem hien tai) tu lich su da co —
    dung khi predict truc tiep (dang du doan tuong lai nen chua co target).
    Tra ve None neu chua du lich su de tinh het feature (con NaN).
    """
    if len(klines) < MIN_HISTORY_FOR_FEATURES:
        return None

    df = _to_float_ohlcv(klines)
    df = _compute_all_features(df)

    last_row = df.iloc[[-1]][FEATURE_COLUMNS]
    if last_row.isna().to_numpy().any():
        return None
    return last_row
