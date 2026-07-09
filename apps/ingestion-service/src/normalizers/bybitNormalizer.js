'use strict';

/**
 * Chuan hoa kline tho tu Bybit v5 (REST /v5/market/kline va WS topic kline.*)
 * ve CUNG shape chung voi Binance (xem klineNormalizer.js).
 *
 * Bybit co 2 dinh dang khac nhau giua REST va WS:
 *
 * REST result.list la MANG cac MANG (moi nen):
 *   [ startTime, open, high, low, close, volume, turnover ]
 *   - startTime: mo cua nen, epoch ms (chuoi). REST khong co co "confirm"
 *     -> coi nhu nen da dong (giong cach Binance REST bootstrap).
 *
 * WS data la MANG cac OBJECT:
 *   { start, end, interval, open, high, low, close, volume, turnover,
 *     confirm (bool), timestamp }
 *   - confirm=true => nen da dong.
 *
 * `symbol`/`interval` truyen vao la format CHUAN NOI BO (BTCUSDT/1m), giu
 * nguyen trong output de dong bo khoa (symbol, interval) toan he thong.
 */

function normalizeBybitRestKline(rawArray, symbol, interval) {
  if (!Array.isArray(rawArray)) {
    throw new TypeError('normalizeBybitRestKline: rawArray phai la mang tu Bybit REST.');
  }

  const [start, open, high, low, close, volume] = rawArray;

  return {
    symbol: String(symbol).toUpperCase(),
    interval,
    openTime: new Date(Number(start)).toISOString(),
    open: Number(open),
    high: Number(high),
    low: Number(low),
    close: Number(close),
    volume: Number(volume),
    // Bybit REST khong tra closeTime rieng cho nen; suy ra tu WS thi co "end".
    // O REST ta khong co end -> tam dat closeTime = openTime (se duoc ban
    // dap lai boi nen WS da dong voi closeTime chinh xac). Chi anh huong
    // hien thi, khong anh huong logic (prediction dung openTime lam khoa).
    closeTime: new Date(Number(start)).toISOString(),
    isClosed: true,
  };
}

function normalizeBybitWsKline(rawObject, symbol, interval) {
  if (!rawObject || typeof rawObject !== 'object' || Array.isArray(rawObject)) {
    throw new TypeError('normalizeBybitWsKline: rawObject phai la object tu Bybit WS.');
  }

  return {
    symbol: String(symbol).toUpperCase(),
    interval,
    openTime: new Date(Number(rawObject.start)).toISOString(),
    open: Number(rawObject.open),
    high: Number(rawObject.high),
    low: Number(rawObject.low),
    close: Number(rawObject.close),
    volume: Number(rawObject.volume),
    closeTime: new Date(Number(rawObject.end)).toISOString(),
    isClosed: Boolean(rawObject.confirm),
  };
}

module.exports = { normalizeBybitRestKline, normalizeBybitWsKline };
