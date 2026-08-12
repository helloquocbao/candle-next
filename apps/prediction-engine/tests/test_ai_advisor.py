"""
Unit tests cho ai_advisor.py (ensemble DeepSeek).

Khong goi network that: requests.post duoc monkeypatch bang stub tra ve
response gia. Chay: cd apps/prediction-engine && pytest
"""

import importlib
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import ai_advisor  # noqa: E402


class _FakeResponse:
    def __init__(self, status_code=200, json_body=None, raise_exc=None):
        self.status_code = status_code
        self._json_body = json_body or {}
        self._raise_exc = raise_exc

    def raise_for_status(self):
        if self._raise_exc is not None:
            raise self._raise_exc

    def json(self):
        return self._json_body


def _chat_response(content: str):
    return _FakeResponse(json_body={"choices": [{"message": {"content": content}}]})


@pytest.fixture(autouse=True)
def _reload_ai_advisor_after_test():
    """Dam bao module doc lai env sach se sau moi test (giong pattern cua
    test_main_config.py) — cac hang so DEEPSEEK_* duoc doc 1 lan luc import."""
    yield
    for key in (
        "DEEPSEEK_ENABLED",
        "DEEPSEEK_API_KEY",
        "DEEPSEEK_WEIGHT",
        "DEEPSEEK_DISAGREEMENT_PENALTY",
    ):
        os.environ.pop(key, None)
    importlib.reload(ai_advisor)


def _some_history(n=10):
    return [{"close": 100.0 + i, "high": 101.0 + i, "low": 99.0 + i} for i in range(n)]


def _quant_signal():
    return {
        "predicted_open": 100.0,
        "predicted_high": 102.0,
        "predicted_low": 98.0,
        "predicted_close": 101.0,
        "confidence": 0.6,
    }


def test_disabled_by_default_returns_none(monkeypatch):
    monkeypatch.delenv("DEEPSEEK_ENABLED", raising=False)
    importlib.reload(ai_advisor)

    assert ai_advisor.DEEPSEEK_ENABLED is False
    assert ai_advisor.get_ai_signal("BTCUSDT", "1m", _some_history(), _quant_signal()) is None


def test_enabled_without_api_key_auto_disables(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_ENABLED", "true")
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    importlib.reload(ai_advisor)

    assert ai_advisor.DEEPSEEK_ENABLED is False


def test_get_ai_signal_returns_none_when_history_too_short(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_ENABLED", "true")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "fake-key")
    importlib.reload(ai_advisor)

    assert ai_advisor.get_ai_signal("BTCUSDT", "1m", _some_history(n=2), _quant_signal()) is None


def test_get_ai_signal_parses_valid_json_response(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_ENABLED", "true")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "fake-key")
    importlib.reload(ai_advisor)

    monkeypatch.setattr(
        ai_advisor.requests,
        "post",
        lambda *a, **k: _chat_response(
            '{"direction": "up", "predicted_change_pct": 0.5, "confidence": 0.7, "reasoning": "xu huong tang"}'
        ),
    )

    signal = ai_advisor.get_ai_signal("BTCUSDT", "1m", _some_history(), _quant_signal())

    assert signal == {
        "direction": "up",
        "predicted_change_pct": 0.5,
        "confidence": 0.7,
        "reasoning": "xu huong tang",
    }


def test_get_ai_signal_parses_response_wrapped_in_markdown_fence(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_ENABLED", "true")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "fake-key")
    importlib.reload(ai_advisor)

    content = (
        "```json\n"
        '{"direction": "down", "predicted_change_pct": -0.3, "confidence": 0.4, "reasoning": "ok"}\n'
        "```"
    )
    monkeypatch.setattr(ai_advisor.requests, "post", lambda *a, **k: _chat_response(content))

    signal = ai_advisor.get_ai_signal("BTCUSDT", "1m", _some_history(), _quant_signal())

    assert signal is not None
    assert signal["direction"] == "down"
    assert signal["predicted_change_pct"] == -0.3


def test_get_ai_signal_returns_none_on_invalid_json(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_ENABLED", "true")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "fake-key")
    importlib.reload(ai_advisor)

    monkeypatch.setattr(ai_advisor.requests, "post", lambda *a, **k: _chat_response("khong phai JSON"))

    assert ai_advisor.get_ai_signal("BTCUSDT", "1m", _some_history(), _quant_signal()) is None


def test_get_ai_signal_returns_none_on_invalid_direction(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_ENABLED", "true")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "fake-key")
    importlib.reload(ai_advisor)

    monkeypatch.setattr(
        ai_advisor.requests,
        "post",
        lambda *a, **k: _chat_response(
            '{"direction": "sideways", "predicted_change_pct": 0.1, "confidence": 0.5}'
        ),
    )

    assert ai_advisor.get_ai_signal("BTCUSDT", "1m", _some_history(), _quant_signal()) is None


def test_get_ai_signal_returns_none_on_network_error(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_ENABLED", "true")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "fake-key")
    importlib.reload(ai_advisor)

    def _raise(*a, **k):
        raise ai_advisor.requests.exceptions.Timeout("timeout")

    monkeypatch.setattr(ai_advisor.requests, "post", _raise)

    assert ai_advisor.get_ai_signal("BTCUSDT", "1m", _some_history(), _quant_signal()) is None


def test_get_ai_signal_returns_none_on_http_error(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_ENABLED", "true")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "fake-key")
    importlib.reload(ai_advisor)

    def _fake_post(*a, **k):
        return _FakeResponse(status_code=401, raise_exc=ai_advisor.requests.exceptions.HTTPError("401"))

    monkeypatch.setattr(ai_advisor.requests, "post", _fake_post)

    assert ai_advisor.get_ai_signal("BTCUSDT", "1m", _some_history(), _quant_signal()) is None


def test_blend_agrees_direction_moves_toward_ai_close(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_WEIGHT", "0.5")
    importlib.reload(ai_advisor)

    quant_signal = _quant_signal()  # predicted_close=101.0, current_close giả định 100.0
    ai_signal = {"direction": "up", "predicted_change_pct": 3.0, "confidence": 0.8, "reasoning": "r"}

    blended = ai_advisor.blend_with_quant_signal(quant_signal, ai_signal, current_close=100.0)

    # ai_close = 100 * 1.03 = 103.0; blended = 0.5*101 + 0.5*103 = 102.0
    assert blended["predicted_close"] == pytest.approx(102.0)
    # Cung chieu (quant: 101>=100 -> up, AI: up) -> khong bi phat disagreement.
    assert blended["confidence"] == pytest.approx(0.5 * 0.6 + 0.5 * 0.8)
    assert blended["ai_direction"] == "up"
    assert blended["ai_disagreement"] is False


def test_blend_disagreement_penalizes_confidence(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_WEIGHT", "0.5")
    monkeypatch.setenv("DEEPSEEK_DISAGREEMENT_PENALTY", "0.5")
    importlib.reload(ai_advisor)

    quant_signal = _quant_signal()  # predicted_close=101.0 >= current_close=100.0 -> quant "up"
    ai_signal = {"direction": "down", "predicted_change_pct": -2.0, "confidence": 0.9, "reasoning": "r"}

    blended = ai_advisor.blend_with_quant_signal(quant_signal, ai_signal, current_close=100.0)

    raw_confidence = 0.5 * 0.6 + 0.5 * 0.9
    assert blended["confidence"] == pytest.approx(raw_confidence * 0.5)
    assert blended["ai_disagreement"] is True


def test_deepseek_weight_out_of_range_raises(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_WEIGHT", "1.5")

    with pytest.raises(ValueError):
        importlib.reload(ai_advisor)
