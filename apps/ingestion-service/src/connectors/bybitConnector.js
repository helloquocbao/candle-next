'use strict';

const { createReconnectingWs } = require('./reconnectingWs');
const { toBybitSymbol, toBybitInterval } = require('../exchanges/symbolFormat');

const BYBIT_REST_BASE_URL = 'https://api.bybit.com';
// spot | linear (USDT perpetual) | inverse. Mac dinh spot de dong bo Binance spot.
const BYBIT_CATEGORY = process.env.BYBIT_CATEGORY || 'spot';
const BYBIT_WS_URL = `wss://stream.bybit.com/v5/public/${BYBIT_CATEGORY}`;
// Bybit khuyen nghi ping moi 20s de giu ket noi.
const BYBIT_PING_INTERVAL_MS = 20000;

/**
 * Lay klines lich su tu Bybit v5 REST de bootstrap.
 * GET /v5/market/kline?category=spot&symbol=BTCUSDT&interval=1&limit=...
 *
 * Bybit gioi han limit toi da 1000; tra ve nen MOI NHAT truoc -> DAO NGUOC
 * ve tang dan thoi gian cho dong bo he thong.
 *
 * @returns {Promise<Array>} mang cac nen tho (array-of-arrays), tang dan thoi gian
 */
async function fetchBybitKlines({ symbol, interval, limit = 500 }) {
  const bybitSymbol = toBybitSymbol(symbol);
  const bybitInterval = toBybitInterval(interval);

  const url = new URL('/v5/market/kline', BYBIT_REST_BASE_URL);
  url.searchParams.set('category', BYBIT_CATEGORY);
  url.searchParams.set('symbol', bybitSymbol);
  url.searchParams.set('interval', bybitInterval);
  url.searchParams.set('limit', String(Math.min(limit, 1000)));

  try {
    const response = await fetch(url.toString(), { method: 'GET' });
    if (!response.ok) {
      const body = await response.text().catch(() => '');
      throw new Error(`Bybit REST HTTP ${response.status} ${response.statusText}: ${body}`);
    }
    const json = await response.json();
    if (json.retCode !== 0 || !json.result || !Array.isArray(json.result.list)) {
      throw new Error(`Bybit REST tra ve loi: retCode=${json.retCode} retMsg=${json.retMsg}`);
    }
    // Bybit tra newest-first -> dao lai thanh oldest-first.
    return json.result.list.slice().reverse();
  } catch (err) {
    console.error(`[bybitRest] Loi khi fetch klines Bybit (${symbol} ${interval}):`, err.message);
    return [];
  }
}

/**
 * Mo WebSocket Bybit kline stream cho 1 cap, tu dong reconnect + ping.
 *
 * @param {Object} opts
 * @param {string} opts.symbol - chuan noi bo, vd "BTCUSDT"
 * @param {string} opts.interval - chuan noi bo, vd "1m"
 * @param {(candleObjects: Array) => void} opts.onCandles - callback nhan MANG
 *   cac object nen tho tu Bybit.
 * @returns {{ close: () => void }}
 */
function connectBybitKlineStream({ symbol, interval, onCandles }) {
  const bybitSymbol = toBybitSymbol(symbol);
  const bybitInterval = toBybitInterval(interval);
  const topic = `kline.${bybitInterval}.${bybitSymbol}`;

  return createReconnectingWs({
    url: BYBIT_WS_URL,
    name: `bybit ${bybitSymbol} ${topic}`,
    pingIntervalMs: BYBIT_PING_INTERVAL_MS,
    buildPing: () => ({ op: 'ping' }),
    onOpen: (ws) => {
      ws.send(JSON.stringify({ op: 'subscribe', args: [topic] }));
    },
    onMessage: (raw) => {
      let msg;
      try {
        msg = JSON.parse(raw);
      } catch {
        return;
      }
      // Phan hoi op (pong/subscribe ack).
      if (msg.op) {
        if (msg.op === 'subscribe' && msg.success === false) {
          console.error(`[bybitWs] Bybit bao loi subscribe (${topic}):`, msg.ret_msg);
        }
        return;
      }
      if (typeof msg.topic === 'string' && msg.topic.startsWith('kline.') && Array.isArray(msg.data)) {
        onCandles(msg.data);
      }
    },
  });
}

module.exports = {
  fetchBybitKlines,
  connectBybitKlineStream,
  BYBIT_REST_BASE_URL,
  BYBIT_WS_URL,
  BYBIT_CATEGORY,
};
