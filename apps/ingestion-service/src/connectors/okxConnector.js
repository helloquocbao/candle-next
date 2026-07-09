'use strict';

const { createReconnectingWs } = require('./reconnectingWs');
const { toOkxInstId, toOkxBar } = require('../exchanges/symbolFormat');

const OKX_REST_BASE_URL = 'https://www.okx.com';
// OKX v5: kenh nen (candle*) nam o endpoint "business", KHONG phai "public"
// (public chi co ticker/orderbook/trades). Subscribe candle* vao /public se
// bao loi "channel doesn't exist".
const OKX_WS_URL = 'wss://ws.okx.com:8443/ws/v5/business';
// OKX dong ket noi neu khong co du lieu/ping trong ~30s -> ping moi 25s.
const OKX_PING_INTERVAL_MS = 25000;

/**
 * Lay klines lich su tu OKX REST de bootstrap.
 * GET /api/v5/market/candles?instId=BTC-USDT&bar=1m&limit=...
 *
 * OKX gioi han limit toi da 300 cho endpoint nay; tra ve nen MOI NHAT truoc
 * (giam dan thoi gian) -> ta DAO NGUOC ve tang dan cho dong bo he thong.
 *
 * @returns {Promise<Array>} mang cac nen tho (array-of-arrays), tang dan thoi gian
 */
async function fetchOkxKlines({ symbol, interval, limit = 300 }) {
  const instId = toOkxInstId(symbol);
  const bar = toOkxBar(interval);

  const url = new URL('/api/v5/market/candles', OKX_REST_BASE_URL);
  url.searchParams.set('instId', instId);
  url.searchParams.set('bar', bar);
  url.searchParams.set('limit', String(Math.min(limit, 300)));

  try {
    const response = await fetch(url.toString(), { method: 'GET' });
    if (!response.ok) {
      const body = await response.text().catch(() => '');
      throw new Error(`OKX REST HTTP ${response.status} ${response.statusText}: ${body}`);
    }
    const json = await response.json();
    if (json.code !== '0' || !Array.isArray(json.data)) {
      throw new Error(`OKX REST tra ve loi: code=${json.code} msg=${json.msg}`);
    }
    // OKX tra newest-first -> dao lai thanh oldest-first.
    return json.data.slice().reverse();
  } catch (err) {
    console.error(`[okxRest] Loi khi fetch klines OKX (${symbol} ${interval}):`, err.message);
    return [];
  }
}

/**
 * Mo WebSocket OKX candle stream cho 1 cap, tu dong reconnect + ping.
 *
 * @param {Object} opts
 * @param {string} opts.symbol - chuan noi bo, vd "BTCUSDT"
 * @param {string} opts.interval - chuan noi bo, vd "1m"
 * @param {(candleRows: Array) => void} opts.onCandles - callback nhan MANG cac
 *   nen tho (array-of-arrays) tu OKX moi khi co update.
 * @returns {{ close: () => void }}
 */
function connectOkxKlineStream({ symbol, interval, onCandles }) {
  const instId = toOkxInstId(symbol);
  const bar = toOkxBar(interval);
  const channel = `candle${bar}`;

  return createReconnectingWs({
    url: OKX_WS_URL,
    name: `okx ${instId} ${channel}`,
    pingIntervalMs: OKX_PING_INTERVAL_MS,
    buildPing: () => 'ping', // OKX yeu cau ping dang text thuan, tra ve 'pong'
    onOpen: (ws) => {
      ws.send(JSON.stringify({ op: 'subscribe', args: [{ channel, instId }] }));
    },
    onMessage: (raw) => {
      if (raw === 'pong') return; // phan hoi heartbeat
      let msg;
      try {
        msg = JSON.parse(raw);
      } catch {
        return; // bo qua message khong phai JSON
      }
      if (msg.event) {
        // ack subscribe / error event
        if (msg.event === 'error') {
          console.error(`[okxWs] OKX bao loi subscribe (${instId} ${channel}):`, msg.msg);
        }
        return;
      }
      if (msg.arg && Array.isArray(msg.data)) {
        onCandles(msg.data);
      }
    },
  });
}

module.exports = {
  fetchOkxKlines,
  connectOkxKlineStream,
  OKX_REST_BASE_URL,
  OKX_WS_URL,
};
