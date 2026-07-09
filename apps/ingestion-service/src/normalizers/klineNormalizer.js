'use strict';

/**
 * Chuan hoa payload kline tho tu Binance (REST hoac WebSocket) thanh 1 object
 * chung dung xuyen suot he thong (ghi DB, publish Redis).
 *
 * Output shape:
 * {
 *   symbol: string,       // vd "BTCUSDT"
 *   interval: string,     // vd "1m"
 *   openTime: string,     // ISO string
 *   open: number,
 *   high: number,
 *   low: number,
 *   close: number,
 *   volume: number,
 *   closeTime: string,    // ISO string
 *   isClosed: boolean,
 * }
 */

/**
 * Binance REST /api/v3/klines tra ve mang array-of-arrays:
 * [
 *   0 openTime, 1 open, 2 high, 3 low, 4 close, 5 volume,
 *   6 closeTime, 7 quoteAssetVolume, 8 numberOfTrades,
 *   9 takerBuyBaseVolume, 10 takerBuyQuoteVolume, 11 ignore
 * ]
 * Cac nen REST tra ve deu la nen da dong (isClosed = true), tru phan tu cuoi
 * cung neu no la nen dang hinh thanh hien tai — nhung Binance REST thuong
 * chi tra ve nen da hoan tat theo `limit`, nen ta mac dinh isClosed = true.
 */
function normalizeRestKline(rawArray, symbol, interval) {
  if (!Array.isArray(rawArray)) {
    throw new TypeError('normalizeRestKline: rawArray phai la mot mang (array) tu Binance REST.');
  }

  const [openTime, open, high, low, close, volume, closeTime] = rawArray;

  return {
    symbol: symbol.toUpperCase(),
    interval,
    openTime: new Date(openTime).toISOString(),
    open: Number(open),
    high: Number(high),
    low: Number(low),
    close: Number(close),
    volume: Number(volume),
    closeTime: new Date(closeTime).toISOString(),
    isClosed: true,
  };
}

/**
 * Binance WebSocket kline stream message co dang:
 * {
 *   e: "kline",
 *   E: 123456789,
 *   s: "BTCUSDT",
 *   k: {
 *     t: 123400000, // open time
 *     T: 123460000, // close time
 *     s: "BTCUSDT",
 *     i: "1m",
 *     o: "0.0010",  // open
 *     c: "0.0020",  // close
 *     h: "0.0025",  // high
 *     l: "0.0015",  // low
 *     v: "1000",    // volume
 *     x: false,     // is this kline closed?
 *     ...
 *   }
 * }
 */
function normalizeWsKline(rawMessage) {
  if (!rawMessage || typeof rawMessage !== 'object' || !rawMessage.k) {
    throw new TypeError('normalizeWsKline: rawMessage khong dung dinh dang kline cua Binance WS.');
  }

  const k = rawMessage.k;

  return {
    symbol: String(k.s).toUpperCase(),
    interval: k.i,
    openTime: new Date(k.t).toISOString(),
    open: Number(k.o),
    high: Number(k.h),
    low: Number(k.l),
    close: Number(k.c),
    volume: Number(k.v),
    closeTime: new Date(k.T).toISOString(),
    isClosed: Boolean(k.x),
  };
}

module.exports = {
  normalizeRestKline,
  normalizeWsKline,
};
