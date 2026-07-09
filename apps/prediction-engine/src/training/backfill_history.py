"""
Backfill lich su nen dai han truc tiep tu Binance REST vao bang `klines`.

Ly do can rieng script nay: bootstrap thong thuong cua ingestion-service chi
lay BOOTSTRAP_LIMIT nen gan nhat (mac dinh 200-500, xem apps/ingestion-service)
— du cho baseline EMA nhung KHONG DU de train model ML (LightGBM can hang
nghin mau de hoc pattern co y nghia thay vi overfit nhieu). Script nay goi
Binance REST /api/v3/klines nhieu lan (moi lan toi da 1000 nen theo gioi han
cua Binance), di CHUYEN TOI (paginate forward) tu 1 thoi diem trong qua khu
cho toi hien tai, ghi (upsert) tung nen vao cung bang `klines` ma he thong
dang dung — khong tao bang/nguon du lieu rieng, tranh lech du lieu.

Chay thu cong (khong nam trong vong lap chinh cua service):
    cd apps/prediction-engine
    python -m training.backfill_history BTCUSDT 1m --candles 5000
    python -m training.backfill_history ETHUSDT 1h --candles 5000

Hoac tu container dang chay:
    docker exec docker-prediction-1 python -m training.backfill_history BTCUSDT 1m --candles 5000
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

sys.path.append(__file__.rsplit("/", 2)[0])  # cho phep `python -m training.xxx` tu thu muc src/

from db import upsert_kline  # noqa: E402

logging.basicConfig(level="INFO", format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("backfill_history")

BINANCE_REST_BASE_URL = "https://api.binance.com"
MAX_CANDLES_PER_REQUEST = 1000
REQUEST_DELAY_SECONDS = 0.3  # tranh cham rate-limit cua Binance REST

# Do dai (ms) cua tung interval — dung de uoc luong startTime ban dau va
# buoc nhay giua cac trang. "1M" (thang) chi la GIA TRI XAP XI (30 ngay) vi
# thang khong co do dai co dinh — chi anh huong ranh gioi trang, khong anh
# huong du lieu thuc te tra ve tu Binance (Binance tu quyet dinh open_time
# that cua tung nen thang).
INTERVAL_MS = {
    "1m": 60_000,
    "3m": 3 * 60_000,
    "5m": 5 * 60_000,
    "15m": 15 * 60_000,
    "30m": 30 * 60_000,
    "1h": 3_600_000,
    "2h": 2 * 3_600_000,
    "4h": 4 * 3_600_000,
    "6h": 6 * 3_600_000,
    "8h": 8 * 3_600_000,
    "12h": 12 * 3_600_000,
    "1d": 86_400_000,
    "3d": 3 * 86_400_000,
    "1w": 7 * 86_400_000,
    "1M": 30 * 86_400_000,
}


def _fetch_klines_page(symbol: str, interval: str, start_time_ms: int, limit: int = MAX_CANDLES_PER_REQUEST):
    params = {
        "symbol": symbol.upper(),
        "interval": interval,
        "startTime": start_time_ms,
        "limit": limit,
    }
    url = f"{BINANCE_REST_BASE_URL}/api/v3/klines?{urllib.parse.urlencode(params)}"
    try:
        with urllib.request.urlopen(url, timeout=15) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Binance REST tra ve loi HTTP {exc.code}: {body}") from exc


def backfill_symbol_interval(symbol: str, interval: str, target_candles: int = 5000) -> int:
    """
    Nap toi da `target_candles` nen gan nhat (co the it hon neu Binance
    khong co du lich su, vd coin moi niem yet) cho 1 cap symbol/interval.

    Returns:
        int: tong so nen da ghi/cap nhat vao DB.
    """
    interval_ms = INTERVAL_MS.get(interval)
    if not interval_ms:
        raise ValueError(f"Khong nhan dien duoc do dai interval '{interval}'")

    now_ms = int(time.time() * 1000)
    cursor_ms = now_ms - target_candles * interval_ms
    total_written = 0

    logger.info(
        "Bat dau backfill %s %s: muc tieu %d nen, tu %s",
        symbol,
        interval,
        target_candles,
        time.strftime("%Y-%m-%d", time.gmtime(cursor_ms / 1000)),
    )

    while True:
        page = _fetch_klines_page(symbol, interval, cursor_ms)
        if not page:
            break

        for row in page:
            open_time_ms, open_, high, low, close, volume, close_time_ms = row[:7]
            upsert_kline(
                symbol=symbol.upper(),
                interval=interval,
                open_time_ms=int(open_time_ms),
                open_=float(open_),
                high=float(high),
                low=float(low),
                close=float(close),
                volume=float(volume),
                close_time_ms=int(close_time_ms),
            )
            total_written += 1

        last_open_time_ms = page[-1][0]
        next_cursor_ms = last_open_time_ms + interval_ms

        if next_cursor_ms >= now_ms or len(page) < MAX_CANDLES_PER_REQUEST:
            break

        cursor_ms = next_cursor_ms
        time.sleep(REQUEST_DELAY_SECONDS)

    logger.info("Hoan tat backfill %s %s: %d nen da ghi/cap nhat.", symbol, interval, total_written)
    return total_written


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("symbol", help='Vd "BTCUSDT"')
    parser.add_argument("interval", help='Vd "1m", "1h", "1d"')
    parser.add_argument("--candles", type=int, default=5000, help="So nen muon nap toi da (mac dinh 5000)")
    args = parser.parse_args()

    backfill_symbol_interval(args.symbol, args.interval, target_candles=args.candles)


if __name__ == "__main__":
    main()
