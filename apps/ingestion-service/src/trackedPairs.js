'use strict';

/**
 * Phan giai danh sach symbol/interval can theo doi, uu tien theo thu tu:
 * 1. env.SYMBOL_PAIRS (vd "BTCUSDT:1m,ETHUSDT:1m") - override thu cong, tien loi cho dev/test.
 * 2. Bang tracked_pairs trong DB (nguon chan ly chung toan he thong,
 *    xem infra/db/migrations/002_tracked_pairs.sql) - qua getTrackedPairsFromDb().
 * 3. env.SYMBOL/env.INTERVAL rieng le (tuong thich nguoc, mac dinh BTCUSDT/1m).
 *
 * San (exchange) duoc chon o buoc dung (index.js): uu tien field `exchange`
 * cua tung cap (neu co, vd tu SYMBOL_PAIRS), roi env.EXCHANGE, cuoi cung mac
 * dinh "binance". Khoa (symbol, interval) giu chuan Binance toan he thong.
 */

function parseSymbolPairsEnv(value) {
  return value
    .split(',')
    .map((entry) => entry.trim())
    .filter(Boolean)
    .map((entry) => {
      // Dinh dang: SYMBOL:interval  hoac  SYMBOL:interval:exchange (tuy chon).
      const [symbol, interval, exchange] = entry.split(':');
      if (!symbol || !interval) {
        throw new Error(
          `SYMBOL_PAIRS: cap khong hop le "${entry}", dinh dang dung la ` +
            `SYMBOL:interval hoac SYMBOL:interval:exchange (vd BTCUSDT:1m hoac BTCUSDT:1m:okx)`
        );
      }
      const pair = { symbol: symbol.toUpperCase(), interval };
      // Chi them field `exchange` khi duoc chi dinh tuong minh — giu output
      // tuong thich nguoc voi cac cap 2 segment (khong sinh key thua).
      if (exchange) pair.exchange = exchange.toLowerCase();
      return pair;
    });
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

/**
 * @param {number} maxAttempts - so lan thu doc DB truoc khi fallback. Can
 *   thiet vi container nay co the khoi dong lai truoc timescaledb (vd sau
 *   khi Docker Desktop restart — moi container co restart policy rieng,
 *   khong dam bao thu tu "cho DB healthy" nhu luc `docker compose up` lan
 *   dau). Neu khong retry, 1 lan DB "starting up" thoang qua se khien
 *   service fallback VINH VIEN ve 1 cap duy nhat cho toi khi restart thu cong.
 */
async function resolveTrackedPairs({
  env = process.env,
  getTrackedPairsFromDb,
  maxAttempts = 5,
  retryDelayMs = 2000,
} = {}) {
  if (env.SYMBOL_PAIRS) {
    const pairs = parseSymbolPairsEnv(env.SYMBOL_PAIRS);
    if (pairs.length) return pairs;
  }

  if (getTrackedPairsFromDb) {
    for (let attempt = 1; attempt <= maxAttempts; attempt += 1) {
      try {
        const pairsFromDb = await getTrackedPairsFromDb();
        if (pairsFromDb.length) return pairsFromDb;
        break; // DB tra ve rong (chua seed) -> khong co ly do gi de retry them
      } catch (err) {
        const isLastAttempt = attempt === maxAttempts;
        console.error(
          `[trackedPairs] Loi doc tracked_pairs tu DB (lan ${attempt}/${maxAttempts})` +
            (isLastAttempt ? ', dung fallback SYMBOL/INTERVAL:' : `, thu lai sau ${retryDelayMs}ms:`),
          err.message
        );
        if (!isLastAttempt) await sleep(retryDelayMs);
      }
    }
  }

  return [
    {
      symbol: env.SYMBOL || 'BTCUSDT',
      interval: env.INTERVAL || '1m',
    },
  ];
}

module.exports = { resolveTrackedPairs, parseSymbolPairsEnv };
