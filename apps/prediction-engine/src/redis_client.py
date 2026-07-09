"""
Redis pub/sub helper cho prediction-engine.

Theo asyncapi.yaml (packages/api-contracts/asyncapi.yaml) va quy uoc dung
chung voi ingestion-service (xem apps/ingestion-service/src/redisPublisher.js):

    - Subscribe:  channel `klines:<symbol>:<interval>`
                  message: { "type": "kline", "data": {...} }

    - Publish:    channel `predictions:<symbol>:<interval>`
                  message: { "type": "prediction", "data": { "predictions": [...] } }
                  ("predictions" la mang N du doan lien tiep — multi-step
                  forecast, xem models/baseline.py::predict_next_n_candles —
                  sap theo thu tu tu gan nhat (t+1) den xa nhat (t+N).)

    - Publish:    channel `accuracy:<symbol>:<interval>`
                  message: { "type": "accuracy_update", "data": {...} }
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Optional

import redis

logger = logging.getLogger(__name__)

_redis_client: Optional[redis.Redis] = None


def get_redis_client() -> redis.Redis:
    """
    Khoi tao (hoac tra ve) client Redis dung chung cho ca service.
    REDIS_URL doc tu bien moi truong.
    """
    global _redis_client
    if _redis_client is not None:
        return _redis_client

    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
    _redis_client = redis.Redis.from_url(redis_url, decode_responses=True)
    return _redis_client


def kline_channel(symbol: str, interval: str) -> str:
    """Ten channel de subscribe kline update."""
    return f"klines:{symbol}:{interval}"


def prediction_channel(symbol: str, interval: str) -> str:
    """Ten channel de publish prediction update."""
    return f"predictions:{symbol}:{interval}"


def accuracy_channel(symbol: str, interval: str) -> str:
    """Ten channel de publish accuracy update."""
    return f"accuracy:{symbol}:{interval}"


def publish_prediction(symbol: str, interval: str, data: dict[str, Any]) -> None:
    """
    Publish batch du doan (multi-step) len channel `predictions:<symbol>:<interval>`.

    Format message theo asyncapi.yaml (channel "prediction", message
    "predictionUpdate"):
        { "type": "prediction", "data": { "predictions": [{ target_time, predicted_open, ... }, ...] } }
    """
    channel = prediction_channel(symbol, interval)
    message = json.dumps({"type": "prediction", "data": data}, default=str)

    try:
        client = get_redis_client()
        client.publish(channel, message)
    except Exception as exc:  # noqa: BLE001 - khong de crash toan bo service
        logger.error("[redis_client] Loi khi publish len channel '%s': %s", channel, exc)


def publish_accuracy(symbol: str, interval: str, data: dict[str, Any]) -> None:
    """
    Publish 1 ban ghi danh gia do chinh xac len channel
    `accuracy:<symbol>:<interval>`.

    Format message theo asyncapi.yaml (channel "accuracy", message
    "accuracyUpdate"):
        { "type": "accuracy_update", "data": {...} }
    """
    channel = accuracy_channel(symbol, interval)
    message = json.dumps({"type": "accuracy_update", "data": data}, default=str)

    try:
        client = get_redis_client()
        client.publish(channel, message)
    except Exception as exc:  # noqa: BLE001 - khong de crash toan bo service
        logger.error("[redis_client] Loi khi publish len channel '%s': %s", channel, exc)
