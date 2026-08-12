"""
Tích hợp AI (DeepSeek Chat API) như 1 TÍN HIỆU BỔ SUNG (ensemble) bên cạnh
mô hình định lượng hiện có (drift EMA + ATR trong forecast_zone.py) — KHÔNG
thay thế, chỉ "nghiêng" dự đoán phiên t+1 (phiên duy nhất đủ gần để đánh giá
sát nhất, và cũng là phiên mà mọi sai lệch được khuếch đại rõ nhất nếu AI sai).

Nguyên tắc fail-safe xuyên suốt module này (giống hệt triết lý "không bịa dữ
liệu" của forecast_zone.py/connectors/vndirect.py trong service này):
    - DEEPSEEK_ENABLED=false (mặc định) -> tắt hoàn toàn, không gọi network.
    - Thiếu DEEPSEEK_API_KEY dù DEEPSEEK_ENABLED=true -> tự động tắt + log warning.
    - Lỗi mạng/timeout/HTTP lỗi/JSON không parse được -> trả về None, KHÔNG raise.
    - Bất kỳ trường hợp None nào ở trên -> caller (main.py) PHẢI fallback về
      đúng nguyên vùng giá đã tính từ forecast_zone.py, không chặn chu kỳ EOD
      (chạy mỗi REFRESH_INTERVAL_SEC, không phải real-time nên có thể chấp
      nhận độ trễ gọi API, nhưng KHÔNG được crash cả chu kỳ vì 1 mã lỗi AI).

Vùng giá sau blend KHÔNG bị kẹp vào biên độ ±7%/phiên của HOSE — mục tiêu là
thể hiện "vùng giá có thể chạy tới trong tương lai" theo model, không phải
biên độ giao dịch lý thuyết của sàn. Riêng % thay đổi mà AI trả về vẫn được
kẹp vào một khoảng rộng (xem SAFETY_CLAMP_PCT) chỉ để chặn giá trị vô lý/
hallucination rõ ràng (ví dụ AI trả về 500%), không phải để mô phỏng biên độ
giao dịch của sàn.
"""

from __future__ import annotations

import json
import logging
import os
import re
from typing import Optional

import requests

logger = logging.getLogger(__name__)


def _env_bool(name: str, default: str) -> bool:
    return os.getenv(name, default).strip().lower() in ("1", "true", "yes", "on")


DEEPSEEK_ENABLED = _env_bool("DEEPSEEK_ENABLED", "false")
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
DEEPSEEK_TIMEOUT_SEC = float(os.getenv("DEEPSEEK_TIMEOUT_SEC", "8"))
# Trọng số giá AI trong blend với model định lượng (0..1) — phần còn lại
# (1 - DEEPSEEK_WEIGHT) là trọng số của forecast_zone.py (drift EMA + ATR).
DEEPSEEK_WEIGHT = float(os.getenv("DEEPSEEK_WEIGHT", "0.35"))
# Phạt (nhân) confidence khi AI và model định lượng BẤT ĐỒNG chiều dự đoán.
DISAGREEMENT_PENALTY = float(os.getenv("DEEPSEEK_DISAGREEMENT_PENALTY", "0.5"))
# Chặn an toàn (KHÔNG liên quan biên độ HOSE) cho % thay đổi AI trả về, chỉ để
# tránh giá trị hallucination phi lý (vd AI trả 500%). Rộng hơn hẳn ±7% vì
# vùng giá dự đoán giờ được phép chạy tự do theo model.
SAFETY_CLAMP_PCT = float(os.getenv("DEEPSEEK_SAFETY_CLAMP_PCT", "30"))

if DEEPSEEK_ENABLED and not DEEPSEEK_API_KEY:
    logger.warning(
        "DEEPSEEK_ENABLED=true nhưng thiếu DEEPSEEK_API_KEY -> tự động tắt AI advisor "
        "(chỉ dùng vùng giá định lượng như trước)."
    )
    DEEPSEEK_ENABLED = False

if not (0.0 <= DEEPSEEK_WEIGHT <= 1.0):
    raise ValueError(f"DEEPSEEK_WEIGHT phải trong khoảng [0, 1], nhận được: {DEEPSEEK_WEIGHT}")


_JSON_BLOCK_RE = re.compile(r"\{.*\}", re.DOTALL)

SYSTEM_PROMPT = (
    "Bạn là một công cụ phân tích kỹ thuật định lượng hỗ trợ hệ thống dự đoán "
    "vùng giá cổ phiếu tự động cho sàn HOSE (Việt Nam). "
    "Chỉ trả về DUY NHẤT 1 đối tượng JSON hợp lệ (không markdown code fence, "
    "không giải thích thêm bên ngoài JSON). Schema bắt buộc:\n"
    '{"direction": "up" | "down" | "flat", '
    '"predicted_change_pct": <số thực, % thay đổi giá dự kiến so với giá đóng cửa gần nhất>, '
    '"confidence": <số thực 0..1>, '
    '"reasoning": "<tối đa 2 câu ngắn, tiếng Việt>"}\n'
    "Đây KHÔNG phải lời khuyên đầu tư — chỉ là 1 ước lượng xác suất dựa trên dữ liệu "
    "định lượng được cung cấp, dùng để kết hợp (ensemble) với 1 model thống kê khác."
)


def _build_user_prompt(symbol: str, history: list[dict], quant_signal: dict) -> str:
    recent = history[-30:]
    closes = [float(c["close"]) for c in recent]
    closes_str = ", ".join(f"{c:.2f}" for c in closes)
    return (
        f"Mã cổ phiếu HOSE: {symbol} (khung thời gian: 1 phiên/ngày).\n"
        f"Giá đóng cửa {len(closes)} phiên gần nhất, thứ tự từ cũ đến mới: [{closes_str}].\n"
        f"Model định lượng (drift EMA + ATR) dự đoán phiên kế "
        f"tiếp: predicted_close={quant_signal['predicted_close']:.2f}, "
        f"confidence={quant_signal['confidence']:.3f}.\n"
        "Dựa trên pattern giá gần đây (có thể đồng ý hoặc không đồng ý với model trên), "
        "hãy ước lượng % thay đổi giá và độ tin cậy của bạn cho phiên KẾ TIẾP, theo đúng "
        "schema JSON đã quy định."
    )


def _parse_response(raw_text: str) -> Optional[dict]:
    match = _JSON_BLOCK_RE.search(raw_text or "")
    if not match:
        return None
    try:
        data = json.loads(match.group(0))
    except (TypeError, ValueError):
        return None

    try:
        direction = str(data["direction"]).strip().lower()
        predicted_change_pct = float(data["predicted_change_pct"])
        confidence = float(data["confidence"])
    except (KeyError, TypeError, ValueError):
        return None

    if direction not in ("up", "down", "flat"):
        return None

    return {
        "direction": direction,
        # Chặn an toàn rộng (không phải biên độ HOSE) chỉ để loại giá trị
        # hallucination phi lý — xem SAFETY_CLAMP_PCT ở đầu module.
        "predicted_change_pct": max(-SAFETY_CLAMP_PCT, min(SAFETY_CLAMP_PCT, predicted_change_pct)),
        "confidence": max(0.0, min(1.0, confidence)),
        "reasoning": str(data.get("reasoning", ""))[:500],
    }


def get_ai_signal(symbol: str, history: list[dict], quant_signal: dict) -> Optional[dict]:
    """
    Gọi DeepSeek Chat API để lấy 1 tín hiệu dự đoán bổ sung cho phiên kế tiếp.

    Trả về None (không bao giờ raise) nếu bị tắt, thiếu key, chưa đủ lịch sử,
    lỗi mạng/timeout, HTTP lỗi, hoặc response không parse được — main.py LUÔN
    phải xử lý được trường hợp None bằng cách dùng nguyên vùng giá định lượng
    (forecast_zone.py), không chặn chu kỳ EOD vì 1 mã lỗi AI.
    """
    if not DEEPSEEK_ENABLED:
        return None
    if len(history) < 5:
        logger.debug("[%s] Chưa đủ lịch sử cho AI advisor (< 5 phiên), bỏ qua.", symbol)
        return None

    payload = {
        "model": DEEPSEEK_MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": _build_user_prompt(symbol, history, quant_signal)},
        ],
        "temperature": 0.2,
        "max_tokens": 300,
        "response_format": {"type": "json_object"},
    }
    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json",
    }

    try:
        response = requests.post(
            f"{DEEPSEEK_BASE_URL.rstrip('/')}/chat/completions",
            json=payload,
            headers=headers,
            timeout=DEEPSEEK_TIMEOUT_SEC,
        )
        response.raise_for_status()
        body = response.json()
        raw_text = body["choices"][0]["message"]["content"]
    except Exception as exc:  # noqa: BLE001 - lỗi AI/mạng không được làm chết chu kỳ EOD
        logger.warning("[%s] Lỗi khi gọi DeepSeek API: %s", symbol, exc)
        return None

    parsed = _parse_response(raw_text)
    if parsed is None:
        logger.warning("[%s] Response DeepSeek không parse được thành JSON hợp lệ: %.200s", symbol, raw_text)
        return None

    logger.info(
        "[%s] AI signal: direction=%s change=%.3f%% confidence=%.3f",
        symbol,
        parsed["direction"],
        parsed["predicted_change_pct"],
        parsed["confidence"],
    )
    return parsed


def blend_with_quant_signal(quant_signal: dict, ai_signal: dict, ref_close: float) -> dict:
    """
    Kết hợp (ensemble) 1 bước dự đoán định lượng (quant_signal — 1 phần tử
    trong zone["predictions"] do forecast_zone.py::build_forecast_zone sinh
    ra) với 1 tín hiệu AI thành 1 bước dự đoán đã blend.

    predicted_open giữ nguyên. predicted_high/low tính lại quanh predicted_close
    MỚI, giữ nguyên độ rộng (half_range) của model định lượng.

    LƯU Ý: không còn ràng buộc kẹp vào phễu ±7% — vùng giá (quant + AI blend)
    được phép chạy tự do theo model, phản ánh "vùng giá có thể chạy tới trong
    tương lai" thay vì biên độ giao dịch lý thuyết của sàn.
    """
    ai_close = ref_close * (1.0 + ai_signal["predicted_change_pct"] / 100.0)
    quant_close = float(quant_signal["predicted_close"])
    blended_close = (1.0 - DEEPSEEK_WEIGHT) * quant_close + DEEPSEEK_WEIGHT * ai_close

    quant_direction = "up" if quant_close >= ref_close else "down"
    disagree = ai_signal["direction"] in ("up", "down") and ai_signal["direction"] != quant_direction

    blended_confidence = (1.0 - DEEPSEEK_WEIGHT) * float(quant_signal["confidence"]) + DEEPSEEK_WEIGHT * float(
        ai_signal["confidence"]
    )
    if disagree:
        blended_confidence *= DISAGREEMENT_PENALTY
    blended_confidence = max(0.0, min(1.0, blended_confidence))

    predicted_open = float(quant_signal["predicted_open"])
    half_range = (float(quant_signal["predicted_high"]) - float(quant_signal["predicted_low"])) / 2.0
    predicted_high = max(predicted_open, blended_close) + half_range
    predicted_low = min(predicted_open, blended_close) - half_range

    result = dict(quant_signal)
    result["predicted_close"] = blended_close
    result["predicted_high"] = predicted_high
    result["predicted_low"] = predicted_low
    result["confidence"] = blended_confidence
    result["ai_direction"] = ai_signal["direction"]
    result["ai_predicted_change_pct"] = ai_signal["predicted_change_pct"]
    result["ai_confidence"] = ai_signal["confidence"]
    result["ai_reasoning"] = ai_signal["reasoning"]
    result["ai_disagreement"] = disagree
    return result
