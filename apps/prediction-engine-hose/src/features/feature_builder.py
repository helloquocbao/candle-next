"""
Xây dựng ma trận feature (cho training) và vector feature cho 1 thời điểm
(cho inference/predict trực tiếp) từ lịch sử OHLCV daily HOSE — port từ
prediction-engine (crypto, features/feature_builder.py), dùng CHUNG 1 danh
sách FEATURE_COLUMNS cho cả 2 trường hợp để tránh train/serve skew (feature
lúc train và lúc predict PHẢI giống hệt nhau).

Khác biệt so với bản crypto: HOSE là daily bar (1 nến/ngày, không phải 1m)
nên lượng lịch sử thực tế ít hơn rất nhiều (vài trăm phiên/mã thay vì hàng
chục nghìn nến). Các period của từng indicator (RSI/MACD/Bollinger...) GIỮ
NGUYÊN như bản gốc (đây là chuẩn kỹ thuật phổ biến, không phụ thuộc
crypto/HOSE), chỉ khác ở chỗ caller (train_lightgbm.py) cần yêu cầu lượng
lịch sử tối thiểu lớn hơn MIN_HISTORY_FOR_FEATURES một khoảng dư đủ để còn
lại vài chục dòng SAU khi warmup dùng cho train + validation có ý nghĩa.
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

# Số phiên "khởi động" tối thiểu trước khi feature đầu tiên hết NaN (chỉ báo
# dài nhất là MACD slow=26+signal=9 ~ 35, Bollinger/volume period=20 — lấy
# dư phòng 40, GIỮ NGUYÊN như bản crypto vì đây là chuẩn kỹ thuật không phụ
# thuộc market). Với daily bar, 40 phiên ~ 2 tháng giao dịch — caller cần
# truyền vào nhiều hơn con số này để còn dữ liệu train/validation thật.
MIN_HISTORY_FOR_FEATURES = 40


def _compute_all_features(df: pd.DataFrame) -> pd.DataFrame:
    """Tính toán và gán toàn bộ cột feature vào df (KHÔNG drop NaN ở đây)."""
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
    """% thay đổi giá close của phiên KẾ TIẾP so với phiên hiện tại (shift -1)."""
    return close.pct_change().shift(-1)


def _to_float_ohlcv(klines: list[dict]) -> pd.DataFrame:
    df = pd.DataFrame(klines).copy()
    for col in ("open", "high", "low", "close", "volume"):
        df[col] = df[col].astype(float)
    return df


def build_training_frame(klines: list[dict]) -> pd.DataFrame:
    """
    klines: danh sách dict có open/high/low/close/volume, SẮP XẾP THỜI GIAN
    TĂNG DẦN (cũ -> mới).

    Trả về DataFrame với các cột FEATURE_COLUMNS + "target_return" (% thay
    đổi giá close của PHIÊN KẾ TIẾP — biến mục tiêu cần dự đoán) + "close"
    (để quy đổi target_return ngược lại thành giá tuyệt đối khi cần) — đã
    drop hết các dòng NaN (warmup đầu chuỗi và dòng cuối cùng không có phiên
    kế tiếp để làm target).
    """
    df = _to_float_ohlcv(klines)
    df = _compute_all_features(df)
    # Dự đoán % THAY ĐỔI GIÁ (return) thay vì giá tuyệt đối — để model học
    # được pattern chung, không phải học lại thang giá riêng của từng mã
    # (VCB ~60 vs VIC ~215), giúp 1 kiến trúc feature dùng chung được.
    df["target_return"] = _next_period_return(df["close"])

    return df[[*FEATURE_COLUMNS, "target_return", "close"]].dropna()


def build_inference_features(klines: list[dict]) -> pd.DataFrame | None:
    """
    Tính feature cho DÒNG CUỐI CÙNG (thời điểm hiện tại) từ lịch sử đã có —
    dùng khi predict trực tiếp (đang dự đoán tương lai nên chưa có target).
    Trả về None nếu chưa đủ lịch sử để tính hết feature (còn NaN).
    """
    if len(klines) < MIN_HISTORY_FOR_FEATURES:
        return None

    df = _to_float_ohlcv(klines)
    df = _compute_all_features(df)

    last_row = df.iloc[[-1]][FEATURE_COLUMNS]
    if last_row.isna().to_numpy().any():
        return None
    return last_row
