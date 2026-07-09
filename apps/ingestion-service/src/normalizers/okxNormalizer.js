'use strict';

/**
 * Chuan hoa kline tho tu OKX (REST /api/v5/market/candles va WS channel
 * candle*) ve CUNG shape chung voi Binance (xem klineNormalizer.js) de
 * downstream (DB/Redis/prediction-engine) khong phai phan biet nguon san.
 *
 * OKX tra ve moi nen la 1 MANG:
 *   [ ts, open, high, low, close, vol, volCcy, volCcyQuote, confirm ]
 *   - ts: mo cua nen, epoch ms (chuoi).
 *   - confirm: "1" = nen da dong, "0" = dang hinh thanh.
 * `symbol`/`interval` truyen vao la format CHUAN NOI BO (BTCUSDT/1m) — ta
 * giu nguyen chung trong output, KHONG dung instId/bar cua OKX, de dong bo
 * khoa (symbol, interval) toan he thong.
 *
 * OKX khong tra san closeTime -> tinh = openTime + do dai interval - 1ms.
 */

const { parseInterval } = require('../exchanges/symbolFormat');

function intervalMillis(interval) {
  const { amount, unit } = parseInterval(interval);
  const UNIT_MS = {
    m: 60 * 1000,
    h: 60 * 60 * 1000,
    d: 24 * 60 * 60 * 1000,
    w: 7 * 24 * 60 * 60 * 1000,
    M: 30 * 24 * 60 * 60 * 1000, // xap xi, chi de tinh closeTime hien thi
  };
  return amount * UNIT_MS[unit];
}

function normalizeOkxKline(rawArray, symbol, interval) {
  if (!Array.isArray(rawArray)) {
    throw new TypeError('normalizeOkxKline: rawArray phai la mang tu OKX.');
  }

  const [ts, open, high, low, close, volume, , , confirm] = rawArray;
  const openMs = Number(ts);
  const closeMs = openMs + intervalMillis(interval) - 1;

  return {
    symbol: String(symbol).toUpperCase(),
    interval,
    openTime: new Date(openMs).toISOString(),
    open: Number(open),
    high: Number(high),
    low: Number(low),
    close: Number(close),
    volume: Number(volume),
    closeTime: new Date(closeMs).toISOString(),
    // REST: nen moi nhat co the chua dong (confirm="0"); WS: confirm bao
    // trang thai truc tiep. Downstream (insertKline) chi ghi khi isClosed.
    isClosed: String(confirm) === '1',
  };
}

module.exports = { normalizeOkxKline, intervalMillis };
