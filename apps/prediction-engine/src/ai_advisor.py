"""
Tich hop AI (DeepSeek Chat API) nhu 1 TIN HIEU BO SUNG (ensemble) ben canh
model dinh luong hien co (baseline EMA hoac LightGBM + Genetic Algorithm) —
KHONG thay the model dinh luong, chi lam "co van" gop them 1 phieu vao du
doan buoc t+1 (buoc duy nhat duoc theo doi de tinh accuracy, xem main.py).

Nguyen tac fail-safe xuyen suot module nay (giong het pattern
models/lightgbm_model.py::load_model fallback ve baseline khi thieu model):
    - DEEPSEEK_ENABLED=false (mac dinh) -> tat hoan toan, khong goi network.
    - Thieu DEEPSEEK_API_KEY du DEEPSEEK_ENABLED=true -> tu dong tat + log warning.
    - Loi mang/timeout/HTTP loi/JSON khong parse duoc -> tra ve None, KHONG raise.
    - Bat ky truong hop None nao o tren -> caller (main.py) phai fallback ve
      dung nguyen tin hieu dinh luong nhu truoc khi co tinh nang nay, dung
      chan luong du doan chinh (real-time) vi 1 loi cua dich vu AI ben ngoai.

Vi sao chi blend buoc t+1 (khong goi API cho ca PREDICTION_HORIZON buoc):
    - Chi buoc t+1 duoc danh gia accuracy thuc te (xem ghi chu
      PREDICTION_HORIZON trong main.py) — goi AI cho cac buoc con lai khong
      danh gia duoc hieu qua thuc su, chi ton chi phi/API rate limit.
    - Giu 1 API call/chu ky du doan giup de throttle (xem
      AI_REFRESH_EVERY_N_CANDLES trong main.py) va de audit (bang ai_signals).
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
# Trong so gia AI trong blend voi model dinh luong (0..1) — phan con lai
# (1 - DEEPSEEK_WEIGHT) la trong so cua model dinh luong (baseline/LightGBM).
# Mac dinh 0.35: giu model dinh luong (da duoc GA toi uu + calibrate) lam
# tin hieu chinh, AI chi "nghieng" ket qua, khong lat nguoc hoan toan.
DEEPSEEK_WEIGHT = float(os.getenv("DEEPSEEK_WEIGHT", "0.35"))
# Phat (nhan) confidence khi AI va model dinh luong BAT DONG chieu du doan —
# 2 nguon doc lap bat dong nghia la ensemble kem chac chan hon ca 2 nguon
# rieng le, phai the hien dieu do o confidence cuoi cung.
DISAGREEMENT_PENALTY = float(os.getenv("DEEPSEEK_DISAGREEMENT_PENALTY", "0.5"))

if DEEPSEEK_ENABLED and not DEEPSEEK_API_KEY:
    logger.warning(
        "DEEPSEEK_ENABLED=true nhung thieu DEEPSEEK_API_KEY -> tu dong tat AI advisor "
        "(chi dung tin hieu dinh luong nhu truoc)."
    )
    DEEPSEEK_ENABLED = False

if not (0.0 <= DEEPSEEK_WEIGHT <= 1.0):
    raise ValueError(f"DEEPSEEK_WEIGHT phai trong khoang [0, 1], nhan duoc: {DEEPSEEK_WEIGHT}")


# Fallback khi response co markdown code fence (```json ... ```) hoac van ban
# giai thich them ngoai JSON du da yeu cau response_format=json_object —
# khong phai model nao/phien ban API nao cung tuan thu strict 100%.
_JSON_BLOCK_RE = re.compile(r"\{.*\}", re.DOTALL)

SYSTEM_PROMPT = (
    "Ban la mot cong cu phan tich ky thuat dinh luong ho tro he thong du doan gia "
    "tu dong. Chi tra ve DUY NHAT 1 doi tuong JSON hop le (khong markdown code "
    "fence, khong giai thich them ben ngoai JSON). Schema bat buoc:\n"
    '{"direction": "up" | "down" | "flat", '
    '"predicted_change_pct": <so thuc, % thay doi gia du kien so voi gia hien tai>, '
    '"confidence": <so thuc 0..1>, '
    '"reasoning": "<toi da 2 cau ngan, tieng Viet>"}\n'
    "Day KHONG phai loi khuyen dau tu — chi la 1 uoc luong xac suat dua tren du "
    "lieu dinh luong duoc cung cap, dung de ket hop (ensemble) voi 1 model thong "
    "ke khac, khong phai khuyen nghi giao dich."
)


def _build_user_prompt(symbol: str, interval: str, history: list[dict], quant_signal: dict) -> str:
    recent = history[-30:]
    closes = [float(c["close"]) for c in recent]
    closes_str = ", ".join(f"{c:.6f}" for c in closes)
    return (
        f"Ma: {symbol}, khung thoi gian: {interval}.\n"
        f"Gia dong cua {len(closes)} nen gan nhat, thu tu tu cu den moi: [{closes_str}].\n"
        f"Model dinh luong (baseline EMA hoac LightGBM da duoc toi uu bang Genetic "
        f"Algorithm) du doan nen ke tiep: predicted_close={quant_signal['predicted_close']:.6f}, "
        f"confidence={quant_signal['confidence']:.3f}.\n"
        "Dua tren pattern gia gan day (co the dong y hoac khong dong y voi model tren), "
        "hay uoc luong % thay doi gia va do tin cay cua ban cho nen KE TIEP, theo dung "
        "schema JSON da quy dinh."
    )


def _parse_response(raw_text: str) -> Optional[dict]:
    """
    Parse noi dung tra ve tu DeepSeek thanh dict {direction, predicted_change_pct,
    confidence, reasoning}. Tra ve None (khong raise) neu khong parse duoc HOAC
    thieu field bat buoc/kieu du lieu sai — caller phai coi day nhu "khong co
    tin hieu AI lan nay", khong phai loi nghiem trong.
    """
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
        "predicted_change_pct": predicted_change_pct,
        "confidence": max(0.0, min(1.0, confidence)),
        "reasoning": str(data.get("reasoning", ""))[:500],
    }


def get_ai_signal(
    symbol: str, interval: str, history: list[dict], quant_signal: dict
) -> Optional[dict]:
    """
    Goi DeepSeek Chat API de lay 1 tin hieu du doan bo sung cho nen ke tiep.

    Tra ve None (khong bao gio raise) neu bi tat, thieu key, chua du lich su,
    loi mang/timeout, HTTP loi, hoac response khong parse duoc — main.py LUON
    phai xu ly duoc truong hop None bang cach dung nguyen tin hieu dinh luong
    (xem PredictionEngine._make_new_prediction), giong het pattern fallback
    cua models/lightgbm_model.py::load_model khi thieu model .txt.
    """
    if not DEEPSEEK_ENABLED:
        return None
    if len(history) < 5:
        logger.debug("[%s:%s] Chua du lich su cho AI advisor (< 5 nen), bo qua.", symbol, interval)
        return None

    payload = {
        "model": DEEPSEEK_MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": _build_user_prompt(symbol, interval, history, quant_signal)},
        ],
        "temperature": 0.2,
        "max_tokens": 300,
        # Yeu cau API tra ve JSON thuan neu duoc ho tro — _parse_response o
        # tren van la luoi an toan thu 2 phong truong hop khong ho tro/khong
        # tuan thu strict (vd model/phien ban khac cua DeepSeek).
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
    except Exception as exc:  # noqa: BLE001 - khong de loi AI/mang lam chet pair thread
        logger.warning("[%s:%s] Loi khi goi DeepSeek API: %s", symbol, interval, exc)
        return None

    parsed = _parse_response(raw_text)
    if parsed is None:
        logger.warning(
            "[%s:%s] Response DeepSeek khong parse duoc thanh JSON hop le: %.200s",
            symbol,
            interval,
            raw_text,
        )
        return None

    logger.info(
        "[%s:%s] AI signal: direction=%s change=%.3f%% confidence=%.3f",
        symbol,
        interval,
        parsed["direction"],
        parsed["predicted_change_pct"],
        parsed["confidence"],
    )
    return parsed


def blend_with_quant_signal(quant_signal: dict, ai_signal: dict, current_close: float) -> dict:
    """
    Ket hop (ensemble) 1 buoc du doan dinh luong (quant_signal — dang tra ve
    tu models/baseline.py::predict_next_candle hoac
    models/lightgbm_model.py::predict_next_candle, TRUOC khi calibrate
    confidence) voi 1 tin hieu AI (ai_signal, tra ve tu get_ai_signal) thanh
    1 buoc du doan da blend, CUNG dang du lieu de main.py xu ly tiep (target_time,
    calibrate_confidence, insert_prediction) khong doi.

    predicted_open giu nguyen (moc gia hien tai, khong phu thuoc model nao).
    predicted_high/low duoc tinh lai quanh predicted_close MOI, giu nguyen do
    rong (half_range) cua model dinh luong — AI khong co uoc luong rieng cho
    bien do high/low, chi uoc luong % thay doi gia dong cua.

    Tra ve dict them cac key "ai_*" (khong co trong quant_signal goc) — main.py
    dung de ghi audit vao bang ai_signals, KHONG duoc ghi truc tiep vao bang
    predictions (insert_prediction chi doc cac key da biet, cac key la se bi
    bo qua an toan neu vo tinh truyen ca dict nay vao).
    """
    ai_close = current_close * (1.0 + ai_signal["predicted_change_pct"] / 100.0)
    quant_close = float(quant_signal["predicted_close"])
    blended_close = (1.0 - DEEPSEEK_WEIGHT) * quant_close + DEEPSEEK_WEIGHT * ai_close

    quant_direction = "up" if quant_close >= current_close else "down"
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
