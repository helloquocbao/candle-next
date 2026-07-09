"""
Phan giai danh sach symbol/interval can theo doi cho prediction-engine.

Cung logic uu tien voi apps/ingestion-service/src/trackedPairs.js, de 2
service luon fan-out dung mot danh sach, khong lech nhau:

1. env TRACKED_PAIRS (vd "BTCUSDT:1m,ETHUSDT:1m") - override thu cong,
   tien loi cho dev/test 1 process theo doi nhieu cap.
2. Bang tracked_pairs trong DB (infra/db/migrations/002_tracked_pairs.sql) -
   nguon cau hinh chung toan he thong, qua get_tracked_pairs_from_db().
3. env SYMBOL/INTERVAL rieng le (tuong thich nguoc, mac dinh BTCUSDT/1m).
"""

from __future__ import annotations

import logging
import os
import time
from typing import Callable, Optional

logger = logging.getLogger(__name__)


def parse_symbol_pairs_env(value: str) -> list[dict[str, str]]:
    pairs: list[dict[str, str]] = []
    for raw_entry in value.split(","):
        entry = raw_entry.strip()
        if not entry:
            continue
        symbol, sep, interval = entry.partition(":")
        symbol = symbol.strip()
        interval = interval.strip()
        if not sep or not symbol or not interval:
            raise ValueError(
                f"TRACKED_PAIRS: cap khong hop le '{entry}', dinh dang dung la "
                "SYMBOL:interval (vd BTCUSDT:1m)"
            )
        pairs.append({"symbol": symbol.upper(), "interval": interval})
    return pairs


def resolve_tracked_pairs(
    env: Optional[dict] = None,
    get_tracked_pairs_from_db: Optional[Callable[[], list[dict[str, str]]]] = None,
    max_attempts: int = 5,
    retry_delay_seconds: float = 2.0,
) -> list[dict[str, str]]:
    """
    max_attempts/retry_delay_seconds: container nay co the khoi dong lai
    truoc timescaledb (vd sau khi Docker Desktop restart — moi container co
    restart policy rieng, khong dam bao thu tu "cho DB healthy" nhu luc
    `docker compose up` lan dau). Neu khong retry, 1 lan DB "starting up"
    thoang qua se khien service fallback VINH VIEN ve 1 cap duy nhat cho toi
    khi restart thu cong.
    """
    env = env if env is not None else os.environ

    raw_pairs = env.get("TRACKED_PAIRS")
    if raw_pairs:
        pairs = parse_symbol_pairs_env(raw_pairs)
        if pairs:
            return pairs

    if get_tracked_pairs_from_db is not None:
        for attempt in range(1, max_attempts + 1):
            try:
                pairs_from_db = get_tracked_pairs_from_db()
                if pairs_from_db:
                    return pairs_from_db
                break  # DB tra ve rong (chua seed) -> khong co ly do de retry them
            except Exception as exc:  # noqa: BLE001 - khong de crash startup
                is_last_attempt = attempt == max_attempts
                if is_last_attempt:
                    logger.error(
                        "Loi doc tracked_pairs tu DB (lan %d/%d), dung fallback SYMBOL/INTERVAL: %s",
                        attempt,
                        max_attempts,
                        exc,
                    )
                else:
                    logger.error(
                        "Loi doc tracked_pairs tu DB (lan %d/%d), thu lai sau %.0fs: %s",
                        attempt,
                        max_attempts,
                        retry_delay_seconds,
                        exc,
                    )
                    time.sleep(retry_delay_seconds)

    return [
        {
            "symbol": env.get("SYMBOL", "BTCUSDT").upper(),
            "interval": env.get("INTERVAL", "1m"),
        }
    ]
