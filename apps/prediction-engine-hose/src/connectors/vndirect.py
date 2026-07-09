"""
Connector dữ liệu HOSE qua VNDIRECT dchart (định dạng TradingView UDF).

Endpoint công khai (không cần key), trả OHLCV theo mảng song song:
    GET https://dchart-api.vndirect.com.vn/dchart/history
        ?symbol=FPT&resolution=D&from=<epoch>&to=<epoch>
    -> {"s":"ok","t":[...],"o":[...],"h":[...],"l":[...],"c":[...],"v":[...]}

`parse_udf` là hàm THUẦN (tách khỏi I/O) để test được với payload mẫu, đưa về
CÙNG shape kline chung của hệ thống (giống ingestion-service crypto) — nhờ đó
DB/Redis/prediction dùng lại được.

Lưu ý pháp lý: dữ liệu thuộc VNDIRECT, dùng cho MVP/hiển thị tham khảo; đọc
ToS trước khi thương mại hoá (xem trao đổi trong dự án).
"""

from __future__ import annotations

import json
import logging
import urllib.parse
import urllib.request
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

VNDIRECT_DCHART_URL = "https://dchart-api.vndirect.com.vn/dchart/history"
DEFAULT_INTERVAL = "1d"
_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36"
)


def _iso_utc(epoch_seconds: int) -> str:
    return datetime.fromtimestamp(int(epoch_seconds), tz=timezone.utc).isoformat()


def parse_udf(payload: dict, symbol: str, interval: str = DEFAULT_INTERVAL) -> list[dict]:
    """
    Chuyển payload UDF của VNDIRECT thành danh sách nến đã chuẩn hoá, SẮP XẾP
    THỜI GIAN TĂNG DẦN (cũ -> mới). Trả về [] nếu status != "ok" hoặc no_data.

    Shape mỗi phần tử (khớp kline chung toàn hệ thống):
        {symbol, interval, openTime, open, high, low, close, volume,
         closeTime, isClosed}
    """
    if not isinstance(payload, dict):
        raise TypeError("parse_udf: payload phải là dict UDF của VNDIRECT.")

    status = payload.get("s")
    if status != "ok":
        # "no_data" hoặc lỗi -> không có nến, caller tự quyết định retry.
        return []

    t = payload.get("t") or []
    o = payload.get("o") or []
    h = payload.get("h") or []
    low_arr = payload.get("l") or []
    c = payload.get("c") or []
    v = payload.get("v") or [0] * len(t)

    n = len(t)
    if not (len(o) == len(h) == len(low_arr) == len(c) == n):
        raise ValueError("parse_udf: các mảng OHLC không cùng độ dài với 't'.")

    sym = symbol.upper()
    rows: list[dict] = []
    for i in range(n):
        open_iso = _iso_utc(t[i])
        rows.append(
            {
                "symbol": sym,
                "interval": interval,
                "openTime": open_iso,
                "open": float(o[i]),
                "high": float(h[i]),
                "low": float(low_arr[i]),
                "close": float(c[i]),
                "volume": float(v[i]) if i < len(v) and v[i] is not None else 0.0,
                # Daily EOD: nến đã đóng; closeTime tạm bằng openTime (chỉ dùng
                # hiển thị, prediction dùng openTime làm khoá).
                "closeTime": open_iso,
                "isClosed": True,
            }
        )

    # VNDIRECT thường trả tăng dần sẵn; sắp xếp lại cho chắc chắn.
    rows.sort(key=lambda r: r["openTime"])
    return rows


def fetch_daily_ohlcv(
    symbol: str, from_ts: int, to_ts: int, interval: str = DEFAULT_INTERVAL
) -> list[dict]:
    """
    Lấy OHLCV daily của 1 mã HOSE trong khoảng [from_ts, to_ts] (epoch giây).
    Trả về danh sách nến chuẩn hoá (tăng dần), hoặc [] nếu lỗi/không có data
    (không raise để không làm chết vòng lặp — caller log & retry).
    """
    params = urllib.parse.urlencode(
        {"symbol": symbol.upper(), "resolution": "D", "from": int(from_ts), "to": int(to_ts)}
    )
    url = f"{VNDIRECT_DCHART_URL}?{params}"
    req = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
        return parse_udf(payload, symbol, interval)
    except Exception:  # noqa: BLE001 - lỗi mạng/parse không được làm chết service
        logger.exception("[vndirect] Lỗi khi lấy OHLCV cho %s", symbol)
        return []
