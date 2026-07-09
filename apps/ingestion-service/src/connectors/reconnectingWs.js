'use strict';

const WebSocket = require('ws');

const INITIAL_BACKOFF_MS = 1000;
const MAX_BACKOFF_MS = 30000;

/**
 * WebSocket tu dong reconnect (exponential backoff) + ping dinh ky (giu ket
 * noi song, tranh bi san dong idle) - dung chung cho OKX/Bybit (2 san deu
 * yeu cau heartbeat, khac voi Binance stream don khong can).
 *
 * @param {Object} opts
 * @param {string} opts.url
 * @param {string} opts.name - ten de log (vd "okx BTC-USDT candle1m")
 * @param {(ws: WebSocket) => void} opts.onOpen - goi khi mo (thuong de gui subscribe)
 * @param {(raw: string, ws: WebSocket) => void} opts.onMessage
 * @param {number} [opts.pingIntervalMs] - neu > 0, gui ping dinh ky
 * @param {() => (string|object)} [opts.buildPing] - noi dung ping (string gui thang, object se JSON.stringify)
 * @returns {{ close: () => void }}
 */
function createReconnectingWs({ url, name, onOpen, onMessage, pingIntervalMs = 0, buildPing }) {
  let ws = null;
  let backoffMs = INITIAL_BACKOFF_MS;
  let reconnectTimer = null;
  let pingTimer = null;
  let isClosedByUser = false;

  function clearTimers() {
    if (reconnectTimer) {
      clearTimeout(reconnectTimer);
      reconnectTimer = null;
    }
    if (pingTimer) {
      clearInterval(pingTimer);
      pingTimer = null;
    }
  }

  function scheduleReconnect() {
    if (isClosedByUser) return;
    console.error(`[reconnectingWs] "${name}" se thu ket noi lai sau ${backoffMs / 1000}s...`);
    reconnectTimer = setTimeout(connect, backoffMs);
    backoffMs = Math.min(backoffMs * 2, MAX_BACKOFF_MS);
  }

  function startPing() {
    if (!pingIntervalMs || !buildPing) return;
    pingTimer = setInterval(() => {
      if (ws && ws.readyState === WebSocket.OPEN) {
        try {
          const payload = buildPing();
          ws.send(typeof payload === 'string' ? payload : JSON.stringify(payload));
        } catch (err) {
          console.error(`[reconnectingWs] "${name}" loi khi gui ping:`, err.message);
        }
      }
    }, pingIntervalMs);
  }

  function connect() {
    try {
      console.log(`[reconnectingWs] "${name}" dang ket noi ${url} ...`);
      ws = new WebSocket(url);

      ws.on('open', () => {
        console.log(`[reconnectingWs] "${name}" da ket noi.`);
        backoffMs = INITIAL_BACKOFF_MS;
        try {
          if (onOpen) onOpen(ws);
        } catch (err) {
          console.error(`[reconnectingWs] "${name}" loi trong onOpen:`, err.message);
        }
        startPing();
      });

      ws.on('message', (data) => {
        try {
          onMessage(data.toString(), ws);
        } catch (err) {
          console.error(`[reconnectingWs] "${name}" loi khi xu ly message:`, err.message);
        }
      });

      ws.on('error', (err) => {
        console.error(`[reconnectingWs] "${name}" loi WebSocket:`, err.message);
      });

      ws.on('close', (code, reason) => {
        console.error(
          `[reconnectingWs] "${name}" ket noi dong (code=${code}, reason=${reason || 'khong ro'}).`
        );
        if (pingTimer) {
          clearInterval(pingTimer);
          pingTimer = null;
        }
        if (!isClosedByUser) scheduleReconnect();
      });
    } catch (err) {
      console.error(`[reconnectingWs] "${name}" loi khi khoi tao ket noi:`, err.message);
      scheduleReconnect();
    }
  }

  connect();

  return {
    close() {
      isClosedByUser = true;
      clearTimers();
      if (ws) {
        try {
          ws.close();
        } catch (err) {
          console.error(`[reconnectingWs] "${name}" loi khi dong:`, err.message);
        }
      }
    },
  };
}

module.exports = { createReconnectingWs, INITIAL_BACKOFF_MS, MAX_BACKOFF_MS };
