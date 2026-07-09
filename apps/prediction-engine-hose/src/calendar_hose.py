"""
Lịch phiên giao dịch HOSE — xác định ngày giao dịch để đặt trục thời gian
cho vùng giá dự đoán (các phiên KẾ TIẾP, bỏ qua cuối tuần & ngày nghỉ lễ).

Khác crypto (chạy 24/7, nến kế tiếp = +interval), CK VN chỉ giao dịch trong
ngày làm việc. Vùng dự đoán N phiên tới phải rơi đúng vào các ngày giao dịch.

Giờ phiên HOSE (Asia/Ho_Chi_Minh, UTC+7):
    Sáng 09:00–11:30, Chiều 13:00–14:45 (ATC tới 14:45; sau đó là phiên
    khớp lệnh định kỳ đóng cửa). Dùng để quyết định thời điểm chạy dự đoán
    (sau giờ đóng cửa) — xem is_after_close.

MVP: chỉ loại trừ THỨ BẢY & CHỦ NHẬT. Ngày nghỉ lễ (Tết âm lịch, lễ dương)
thay đổi theo năm nên được truyền vào qua tham số `holidays` (set các
datetime.date) — bổ sung danh sách thật sau, không hard-code trong MVP.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from typing import Iterable, Optional

# Giờ đóng cửa phiên chiều HOSE (kết thúc ATC). Dùng để biết đã hết phiên
# trong ngày hay chưa (chạy dự đoán EOD sau mốc này).
HOSE_CLOSE_TIME = time(14, 45)
HOSE_OPEN_TIME = time(9, 0)


def is_weekend(d: date) -> bool:
    """Thứ 7 (5) hoặc Chủ nhật (6) theo weekday()."""
    return d.weekday() >= 5


def is_trading_day(d: date, holidays: Optional[Iterable[date]] = None) -> bool:
    """
    Là ngày giao dịch HOSE? (không phải cuối tuần và không nằm trong danh
    sách nghỉ lễ). `holidays` mặc định rỗng (MVP chỉ chặn cuối tuần).
    """
    if is_weekend(d):
        return False
    if holidays and d in set(holidays):
        return False
    return True


def next_trading_day(d: date, holidays: Optional[Iterable[date]] = None) -> date:
    """Ngày giao dịch đầu tiên SAU ngày `d`."""
    holiday_set = set(holidays) if holidays else set()
    cur = d + timedelta(days=1)
    while not is_trading_day(cur, holiday_set):
        cur += timedelta(days=1)
    return cur


def next_n_trading_days(
    from_date: date, n: int, holidays: Optional[Iterable[date]] = None
) -> list[date]:
    """
    N ngày giao dịch kế tiếp sau `from_date` — chính là trục thời gian cho
    vùng giá dự đoán (t+1 … t+N).

    Raises:
        ValueError: nếu n < 1.
    """
    if n < 1:
        raise ValueError("next_n_trading_days: n phải >= 1.")
    holiday_set = set(holidays) if holidays else set()
    result: list[date] = []
    cur = from_date
    for _ in range(n):
        cur = next_trading_day(cur, holiday_set)
        result.append(cur)
    return result


def is_after_close(dt: datetime) -> bool:
    """
    Đã qua giờ đóng cửa HOSE trong ngày giao dịch đó chưa? Dùng để quyết
    định thời điểm chạy dự đoán EOD (chỉ chạy khi phiên đã kết thúc để có giá
    đóng cửa cuối cùng). `dt` giả định theo giờ VN (UTC+7).
    """
    return dt.time() >= HOSE_CLOSE_TIME
