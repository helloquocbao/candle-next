"""
Unit tests cho tracked_pairs.py — phan giai danh sach symbol/interval theo
thu tu uu tien: env TRACKED_PAIRS -> DB -> env SYMBOL/INTERVAL rieng le.

Chạy: cd apps/prediction-engine && pytest
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from tracked_pairs import parse_symbol_pairs_env, resolve_tracked_pairs  # noqa: E402


def test_parse_symbol_pairs_env_parses_list():
    pairs = parse_symbol_pairs_env("BTCUSDT:1m, ethusdt:5m ,SOLUSDT:1m")
    assert pairs == [
        {"symbol": "BTCUSDT", "interval": "1m"},
        {"symbol": "ETHUSDT", "interval": "5m"},
        {"symbol": "SOLUSDT", "interval": "1m"},
    ]


def test_parse_symbol_pairs_env_raises_on_missing_interval():
    with pytest.raises(ValueError):
        parse_symbol_pairs_env("BTCUSDT")


def test_resolve_tracked_pairs_prefers_env_override():
    def boom():
        raise AssertionError("khong duoc goi khi da co TRACKED_PAIRS")

    pairs = resolve_tracked_pairs(
        env={"TRACKED_PAIRS": "BTCUSDT:1m,ETHUSDT:1m"},
        get_tracked_pairs_from_db=boom,
    )
    assert pairs == [
        {"symbol": "BTCUSDT", "interval": "1m"},
        {"symbol": "ETHUSDT", "interval": "1m"},
    ]


def test_resolve_tracked_pairs_reads_from_db_when_no_env_override():
    pairs = resolve_tracked_pairs(
        env={},
        get_tracked_pairs_from_db=lambda: [
            {"symbol": "BTCUSDT", "interval": "1m"},
            {"symbol": "SOLUSDT", "interval": "1m"},
        ],
    )
    assert pairs == [
        {"symbol": "BTCUSDT", "interval": "1m"},
        {"symbol": "SOLUSDT", "interval": "1m"},
    ]


def test_resolve_tracked_pairs_falls_back_after_exhausting_retries():
    calls = {"count": 0}

    def boom():
        calls["count"] += 1
        raise RuntimeError("DB down")

    pairs = resolve_tracked_pairs(
        env={"SYMBOL": "ETHUSDT", "INTERVAL": "5m"},
        get_tracked_pairs_from_db=boom,
        max_attempts=3,
        retry_delay_seconds=0,
    )
    assert pairs == [{"symbol": "ETHUSDT", "interval": "5m"}]
    assert calls["count"] == 3


def test_resolve_tracked_pairs_retries_and_succeeds_after_db_not_ready():
    calls = {"count": 0}

    def flaky():
        calls["count"] += 1
        if calls["count"] < 3:
            raise RuntimeError("the database system is starting up")
        return [{"symbol": "BTCUSDT", "interval": "1m"}]

    pairs = resolve_tracked_pairs(
        env={},
        get_tracked_pairs_from_db=flaky,
        max_attempts=5,
        retry_delay_seconds=0,
    )
    assert pairs == [{"symbol": "BTCUSDT", "interval": "1m"}]
    assert calls["count"] == 3


def test_resolve_tracked_pairs_default_when_nothing_configured():
    pairs = resolve_tracked_pairs(env={})
    assert pairs == [{"symbol": "BTCUSDT", "interval": "1m"}]
