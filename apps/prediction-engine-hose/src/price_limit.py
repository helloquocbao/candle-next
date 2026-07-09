"""
Phễu trần/sàn HOSE — ràng buộc biên độ ±7%/phiên cho vùng giá dự đoán.

Sàn HOSE giới hạn giá mỗi phiên dao động tối đa ±7% quanh GIÁ THAM CHIẾU
(thường là giá đóng cửa phiên liền trước). Vì vậy vùng giá dự đoán N phiên
tới KHÔNG được vẽ ra mức bất khả thi — mỗi bước phải nằm trong phễu lũy tiến:

    biên trên sau k phiên = ref × (1 + 0.07)^k
    biên dưới sau k phiên = ref × (1 - 0.07)^k

Module thuần (pure) — không I/O, dễ test độc lập. Chưa xử lý bước giá (tick
size) làm tròn theo quy định HOSE; để tối giản MVP dùng số thực, làm tròn
tick có thể bổ sung sau (xem ghi chú round_to_tick).
"""

from __future__ import annotations

# Biên độ dao động tối đa mỗi phiên trên HOSE (±7%). Các sàn khác (HNX ±10%,
# UPCOM ±15%) KHÔNG nằm trong phạm vi MVP này — xem quyết định "chỉ HOSE".
HOSE_DAILY_LIMIT = 0.07


def daily_band(ref_price: float, limit: float = HOSE_DAILY_LIMIT) -> tuple[float, float]:
    """
    Trả về (giá sàn, giá trần) của MỘT phiên quanh giá tham chiếu.

    Raises:
        ValueError: nếu ref_price <= 0.
    """
    if ref_price <= 0:
        raise ValueError("daily_band: ref_price phải > 0.")
    return ref_price * (1.0 - limit), ref_price * (1.0 + limit)


def funnel_bounds(
    ref_close: float, step: int, limit: float = HOSE_DAILY_LIMIT
) -> tuple[float, float]:
    """
    Biên (sàn, trần) LŨY TIẾN sau `step` phiên kể từ giá tham chiếu ref_close.

    step = 1 là phiên kế tiếp (t+1). Do mỗi phiên chỉ ±limit so với phiên
    trước, biên tối đa sau k phiên là ref × (1 ± limit)^k — tạo thành "phễu"
    mở rộng dần.

    Raises:
        ValueError: nếu step < 1 hoặc ref_close <= 0.
    """
    if step < 1:
        raise ValueError("funnel_bounds: step phải >= 1.")
    if ref_close <= 0:
        raise ValueError("funnel_bounds: ref_close phải > 0.")
    floor = ref_close * (1.0 - limit) ** step
    ceiling = ref_close * (1.0 + limit) ** step
    return floor, ceiling


def clamp(value: float, low: float, high: float) -> float:
    """Kẹp `value` vào [low, high]."""
    return max(low, min(high, value))


def clamp_forecast_step(
    predicted_low: float,
    predicted_high: float,
    predicted_close: float,
    ref_close: float,
    step: int,
    limit: float = HOSE_DAILY_LIMIT,
) -> dict:
    """
    Kẹp một bước dự đoán (low/high/close) vào phễu trần/sàn HOSE tại `step`.

    Đây là điểm mấu chốt để vùng giá tương lai không vượt biên độ lý thuyết:
    dải model (ATR...) giao với phễu ±7% lũy tiến.

    Returns:
        dict: {predicted_low, predicted_high, predicted_close, floor, ceiling}
        với floor/ceiling là biên phễu tại bước đó (tiện vẽ khung tham chiếu).
    """
    floor, ceiling = funnel_bounds(ref_close, step, limit)
    low = clamp(predicted_low, floor, ceiling)
    high = clamp(predicted_high, floor, ceiling)
    # Đảm bảo low <= high sau khi kẹp (nếu model đảo ngược).
    if low > high:
        low, high = high, low
    return {
        "predicted_low": low,
        "predicted_high": high,
        "predicted_close": clamp(predicted_close, floor, ceiling),
        "floor": floor,
        "ceiling": ceiling,
    }


def pct_change(price: float, ref: float) -> float:
    """% thay đổi của `price` so với `ref` (dương = tăng), dùng cho nhãn vùng."""
    if ref <= 0:
        raise ValueError("pct_change: ref phải > 0.")
    return (price / ref - 1.0) * 100.0
