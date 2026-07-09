"""Unit test cho src/connectors/vndirect.py — parse UDF (thuần, không mạng)."""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from connectors.vndirect import parse_udf  # noqa: E402

SAMPLE_OK = {
    "s": "ok",
    "t": [1778457600, 1778544000],
    "o": [68.5, 69.0],
    "h": [70.0, 71.2],
    "l": [68.0, 68.8],
    "c": [69.048, 69.64],
    "v": [1234567, 2345678],
}


def test_parse_udf_maps_to_common_shape():
    rows = parse_udf(SAMPLE_OK, "fpt")
    assert len(rows) == 2
    r = rows[0]
    assert r["symbol"] == "FPT"
    assert r["interval"] == "1d"
    assert r["open"] == 68.5
    assert r["high"] == 70.0
    assert r["low"] == 68.0
    assert r["close"] == 69.048
    assert r["volume"] == 1234567.0
    assert r["isClosed"] is True
    assert isinstance(r["openTime"], str)


def test_parse_udf_sorted_ascending():
    rows = parse_udf(SAMPLE_OK, "FPT")
    assert rows[0]["openTime"] < rows[1]["openTime"]


def test_parse_udf_no_data_returns_empty():
    assert parse_udf({"s": "no_data"}, "FPT") == []
    assert parse_udf({"s": "error"}, "FPT") == []


def test_parse_udf_missing_volume_defaults_zero():
    payload = dict(SAMPLE_OK)
    del payload["v"]
    rows = parse_udf(payload, "FPT")
    assert all(r["volume"] == 0.0 for r in rows)


def test_parse_udf_mismatched_arrays_raises():
    bad = dict(SAMPLE_OK)
    bad["c"] = [69.048]  # ngắn hơn t
    with pytest.raises(ValueError):
        parse_udf(bad, "FPT")


def test_parse_udf_rejects_non_dict():
    with pytest.raises(TypeError):
        parse_udf([], "FPT")
