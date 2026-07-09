'use strict';

const WebSocket = require('ws');

const BINANCE_WS_BASE_URL = 'wss://stream.binance.com:9443/ws';

const INITIAL_BACKOFF_MS = 1000; // 1s
const MAX_BACKOFF_MS = 30000; // 30s

/**
 * Mo ket noi WebSocket toi Binance kline stream, tu dong reconnect voi
 * exponential backoff (1s -> 2s -> 4s ... toi da 30s) khi connection dong/loi.
 *
 * @param {Object} options
 * @param {string} options.symbol - vd "BTCUSDT"
 * @param {string} options.interval - vd "1m"
 * @param {(rawMessage: object) => void} options.onKline - callback moi khi nhan duoc message kline
 * @returns {{ close: () => void }} handle de chu dong dong ket noi (dung khi shutdown)
 */
function connectBinanceKlineStream({ symbol, interval, onKline }) {
  if (!symbol || !interval) {
    throw new Error('connectBinanceKlineStream: thieu tham so bat buoc symbol/interval.');
  }

  const streamName = `${symbol.toLowerCase()}@kline_${interval}`;
  const wsUrl = `${BINANCE_WS_BASE_URL}/${streamName}`;

  let ws = null;
  let backoffMs = INITIAL_BACKOFF_MS;
  let reconnectTimer = null;
  let isClosedByUser = false;

  function scheduleReconnect() {
    if (isClosedByUser) return;

    console.error(
      `[binanceWs] Se thu ket noi lai stream "${streamName}" sau ${backoffMs / 1000}s...`
    );

    reconnectTimer = setTimeout(() => {
      connect();
    }, backoffMs);

    // Tang backoff theo cap so nhan, gioi han o MAX_BACKOFF_MS
    backoffMs = Math.min(backoffMs * 2, MAX_BACKOFF_MS);
  }

  function connect() {
    try {
      console.log(`[binanceWs] Dang ket noi toi ${wsUrl} ...`);
      ws = new WebSocket(wsUrl);

      ws.on('open', () => {
        console.log(`[binanceWs] Da ket noi thanh cong stream "${streamName}".`);
        // Reset backoff khi ket noi thanh cong
        backoffMs = INITIAL_BACKOFF_MS;
      });

      ws.on('message', (data) => {
        try {
          const parsed = JSON.parse(data.toString());
          onKline(parsed);
        } catch (err) {
          console.error('[binanceWs] Loi parse message tu Binance WS:', err.message);
        }
      });

      ws.on('error', (err) => {
        console.error(`[binanceWs] Loi WebSocket tren stream "${streamName}":`, err.message);
        // 'close' event se duoc kich hoat sau 'error', reconnect se xu ly o do.
      });

      ws.on('close', (code, reason) => {
        console.error(
          `[binanceWs] Ket noi stream "${streamName}" da dong (code=${code}, reason=${reason || 'khong ro'}).`
        );
        if (!isClosedByUser) {
          scheduleReconnect();
        }
      });
    } catch (err) {
      console.error(`[binanceWs] Loi khong xac dinh khi khoi tao ket noi WS:`, err.message);
      scheduleReconnect();
    }
  }

  connect();

  return {
    close() {
      isClosedByUser = true;
      if (reconnectTimer) {
        clearTimeout(reconnectTimer);
        reconnectTimer = null;
      }
      if (ws) {
        try {
          ws.close();
        } catch (err) {
          console.error('[binanceWs] Loi khi dong ket noi WS:', err.message);
        }
      }
    },
  };
}

module.exports = {
  connectBinanceKlineStream,
  BINANCE_WS_BASE_URL,
};
