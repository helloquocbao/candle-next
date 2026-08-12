"""
Unit tests cho ai_advisor.py (ensemble DeepSeek) — prediction-engine-hose.

Không gọi network thật: requests.post được monkeypatch bằng stub trả về
response giả. Chạy: cd apps/prediction-engine-hose && pytest
"""

import importlib
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import ai_advisor  # noqa: E402


class _FakeResponse:
    def __init__(self, json_body=None, raise_exc=None):
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
    yield
    for key in ("DEEPSEEK_ENABLED", "DEEPSEEK_API_KEY", "DEEPSEEK_WEIGHT", "DEEPSEEK_DISAGREEMENT_PENALTY"):
        os.environ.pop(key, None)
    importlib.reload(ai_advisor)


def _some_history(n=10):
    return [{"close": 20.0 + 0.1 * i} for i in range(n)]


def _quant_signal():
    return {
        "predicted_open": 20.0,
        "predicted_high": 20.6,
        "predicted_low": 19.6,
        "predicted_close": 20.3,
        "confidence": 0.5,
    }


def test_disabled_by_default_returns_none(monkeypatch):
    monkeypatch.delenv("DEEPSEEK_ENABLED", raising=False)
    importlib.reload(ai_advisor)

    assert ai_advisor.get_ai_signal("FPT", _some_history(), _quant_signal()) is None


def test_predicted_change_pct_is_clamped_to_safety_limit(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_ENABLED", "true")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "fake-key")
    importlib.reload(ai_advisor)

    monkeypatch.setattr(
        ai_advisor.requests,
        "post",
        lambda *a, **k: _chat_response(
            '{"direction": "up", "predicted_change_pct": 500.0, "confidence": 0.9, "reasoning": "r"}'
        ),
    )

    signal = ai_advisor.get_ai_signal("FPT", _some_history(), _quant_signal())

    assert signal is not None
    # Không còn giới hạn theo biên độ HOSE ±7% — chỉ chặn an toàn giá trị
    # hallucination phi lý (mặc định ±30%, xem SAFETY_CLAMP_PCT).
    assert signal["predicted_change_pct"] == ai_advisor.SAFETY_CLAMP_PCT


def test_predicted_change_pct_within_safety_limit_not_altered(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_ENABLED", "true")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "fake-key")
    importlib.reload(ai_advisor)

    monkeypatch.setattr(
        ai_advisor.requests,
        "post",
        lambda *a, **k: _chat_response(
            '{"direction": "up", "predicted_change_pct": 12.0, "confidence": 0.9, "reasoning": "r"}'
        ),
    )

    signal = ai_advisor.get_ai_signal("FPT", _some_history(), _quant_signal())

    assert signal is not None
    # 12% vượt biên độ HOSE ±7% cũ nhưng vẫn trong SAFETY_CLAMP_PCT -> giữ nguyên.
    assert signal["predicted_change_pct"] == 12.0


def test_get_ai_signal_returns_none_on_network_error(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_ENABLED", "true")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "fake-key")
    importlib.reload(ai_advisor)

    def _raise(*a, **k):
        raise ai_advisor.requests.exceptions.Timeout("timeout")

    monkeypatch.setattr(ai_advisor.requests, "post", _raise)

    assert ai_advisor.get_ai_signal("FPT", _some_history(), _quant_signal()) is None


def test_blend_with_quant_signal_agrees_direction(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_WEIGHT", "0.5")
    importlib.reload(ai_advisor)

    ai_signal = {"direction": "up", "predicted_change_pct": 2.0, "confidence": 0.8, "reasoning": "r"}
    blended = ai_advisor.blend_with_quant_signal(_quant_signal(), ai_signal, ref_close=20.0)

    # ai_close = 20 * 1.02 = 20.4; quant_close=20.3 -> blended=(20.3+20.4)/2=20.35
    assert blended["predicted_close"] == pytest.approx(20.35)
    assert blended["ai_disagreement"] is False


def test_blend_with_quant_signal_disagreement_penalizes_confidence(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_WEIGHT", "0.5")
    monkeypatch.setenv("DEEPSEEK_DISAGREEMENT_PENALTY", "0.5")
    importlib.reload(ai_advisor)

    # quant_close=20.3 >= ref_close=20.0 -> quant huong "up"; AI noi "down" -> bat dong.
    ai_signal = {"direction": "down", "predicted_change_pct": -1.0, "confidence": 0.9, "reasoning": "r"}
    blended = ai_advisor.blend_with_quant_signal(_quant_signal(), ai_signal, ref_close=20.0)

    raw_confidence = 0.5 * 0.5 + 0.5 * 0.9
    assert blended["confidence"] == pytest.approx(raw_confidence * 0.5)
    assert blended["ai_disagreement"] is True
