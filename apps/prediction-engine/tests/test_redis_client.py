"""
Unit tests cho redis_client.py — dac biet la duong loi (Redis khong ket noi
duoc thi publish_* phai NUOT loi, khong duoc raise va lam crash main.py).
Chua tung co test nao cho module nay.

Chạy: cd apps/prediction-engine && pytest
"""

import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import redis_client as redis_client_module  # noqa: E402


@pytest.fixture(autouse=True)
def _reset_client_cache():
    redis_client_module._redis_client = None
    yield
    redis_client_module._redis_client = None


class FakeRedis:
    def __init__(self):
        self.published: list[tuple[str, str]] = []

    def publish(self, channel, message):
        self.published.append((channel, message))


class BrokenRedis:
    def publish(self, *_args, **_kwargs):
        raise ConnectionError("khong ket noi duoc Redis")


def test_kline_channel_format():
    assert redis_client_module.kline_channel("BTCUSDT", "1m") == "klines:BTCUSDT:1m"


def test_prediction_channel_format():
    assert redis_client_module.prediction_channel("BTCUSDT", "1m") == "predictions:BTCUSDT:1m"


def test_accuracy_channel_format():
    assert redis_client_module.accuracy_channel("BTCUSDT", "1m") == "accuracy:BTCUSDT:1m"


def test_get_redis_client_reuses_cached_client():
    fake = FakeRedis()
    redis_client_module._redis_client = fake

    assert redis_client_module.get_redis_client() is fake


def test_get_redis_client_creates_via_from_url(monkeypatch):
    created = {}

    def fake_from_url(url, decode_responses):
        created["url"] = url
        created["decode_responses"] = decode_responses
        return FakeRedis()

    monkeypatch.setattr(redis_client_module.redis.Redis, "from_url", fake_from_url)
    monkeypatch.setenv("REDIS_URL", "redis://example-host:6379")

    client = redis_client_module.get_redis_client()

    assert created["url"] == "redis://example-host:6379"
    assert created["decode_responses"] is True
    assert isinstance(client, FakeRedis)


def test_publish_prediction_sends_correct_channel_and_payload(monkeypatch):
    fake = FakeRedis()
    monkeypatch.setattr(redis_client_module, "get_redis_client", lambda: fake)

    redis_client_module.publish_prediction("BTCUSDT", "1m", {"predicted_close": 100.0})

    assert len(fake.published) == 1
    channel, message = fake.published[0]
    assert channel == "predictions:BTCUSDT:1m"
    assert json.loads(message) == {"type": "prediction", "data": {"predicted_close": 100.0}}


def test_publish_accuracy_sends_correct_channel_and_payload(monkeypatch):
    fake = FakeRedis()
    monkeypatch.setattr(redis_client_module, "get_redis_client", lambda: fake)

    redis_client_module.publish_accuracy("BTCUSDT", "1m", {"accuracy_pct": 99.0})

    channel, message = fake.published[0]
    assert channel == "accuracy:BTCUSDT:1m"
    assert json.loads(message) == {"type": "accuracy_update", "data": {"accuracy_pct": 99.0}}


def test_publish_prediction_does_not_raise_when_redis_unavailable(monkeypatch):
    monkeypatch.setattr(redis_client_module, "get_redis_client", lambda: BrokenRedis())

    # Khong duoc raise — publish la best-effort (main.py khong duoc crash vi mat Redis).
    redis_client_module.publish_prediction("BTCUSDT", "1m", {"predicted_close": 100.0})


def test_publish_accuracy_does_not_raise_when_redis_unavailable(monkeypatch):
    monkeypatch.setattr(redis_client_module, "get_redis_client", lambda: BrokenRedis())

    redis_client_module.publish_accuracy("BTCUSDT", "1m", {"accuracy_pct": 99.0})
