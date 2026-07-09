'use strict';

/**
 * Registry cac san giao dich (exchange adapter). Moi adapter phoi hop
 * connector (REST/WS rieng cua san) voi normalizer tuong ung, phoi bay CUNG
 * 1 interface de index.js hoan toan KHONG can biet dang lam viec voi san nao:
 *
 *   fetchHistory({ symbol, interval, limit }) -> Promise<Array<normalized>>
 *   connectStream({ symbol, interval, onKline }) -> { close }
 *
 * `normalized` la shape chung (xem normalizers/klineNormalizer.js). `symbol`/
 * `interval` luon la format CHUAN NOI BO (BTCUSDT/1m); adapter tu convert
 * sang format rieng cua san ben trong.
 */

const { fetchKlines } = require('../connectors/binanceRest');
const { connectBinanceKlineStream } = require('../connectors/binanceWs');
const { normalizeRestKline, normalizeWsKline } = require('../normalizers/klineNormalizer');

const { fetchOkxKlines, connectOkxKlineStream } = require('../connectors/okxConnector');
const { normalizeOkxKline } = require('../normalizers/okxNormalizer');

const { fetchBybitKlines, connectBybitKlineStream } = require('../connectors/bybitConnector');
const {
  normalizeBybitRestKline,
  normalizeBybitWsKline,
} = require('../normalizers/bybitNormalizer');

const binance = {
  name: 'binance',
  async fetchHistory({ symbol, interval, limit }) {
    const raw = await fetchKlines({ symbol, interval, limit });
    return raw.map((r) => normalizeRestKline(r, symbol, interval));
  },
  connectStream({ symbol, interval, onKline }) {
    return connectBinanceKlineStream({
      symbol,
      interval,
      onKline: (rawMessage) => {
        let normalized;
        try {
          normalized = normalizeWsKline(rawMessage);
        } catch (err) {
          console.error(`[exchanges/binance] Loi chuan hoa WS (${symbol} ${interval}):`, err.message);
          return;
        }
        onKline(normalized);
      },
    });
  },
};

const okx = {
  name: 'okx',
  async fetchHistory({ symbol, interval, limit }) {
    const raw = await fetchOkxKlines({ symbol, interval, limit });
    return raw.map((row) => normalizeOkxKline(row, symbol, interval));
  },
  connectStream({ symbol, interval, onKline }) {
    return connectOkxKlineStream({
      symbol,
      interval,
      onCandles: (rows) => {
        for (const row of rows) {
          try {
            onKline(normalizeOkxKline(row, symbol, interval));
          } catch (err) {
            console.error(`[exchanges/okx] Loi chuan hoa WS (${symbol} ${interval}):`, err.message);
          }
        }
      },
    });
  },
};

const bybit = {
  name: 'bybit',
  async fetchHistory({ symbol, interval, limit }) {
    const raw = await fetchBybitKlines({ symbol, interval, limit });
    return raw.map((row) => normalizeBybitRestKline(row, symbol, interval));
  },
  connectStream({ symbol, interval, onKline }) {
    return connectBybitKlineStream({
      symbol,
      interval,
      onCandles: (rows) => {
        for (const row of rows) {
          try {
            onKline(normalizeBybitWsKline(row, symbol, interval));
          } catch (err) {
            console.error(`[exchanges/bybit] Loi chuan hoa WS (${symbol} ${interval}):`, err.message);
          }
        }
      },
    });
  },
};

const REGISTRY = { binance, okx, bybit };

const DEFAULT_EXCHANGE = 'binance';

/**
 * Tra ve adapter cho san `name` (khong phan biet hoa/thuong). Neu khong ho
 * tro -> canh bao va fallback ve Binance (khong bao gio crash chi vi cau
 * hinh sai ten san).
 */
function getExchangeAdapter(name) {
  const key = String(name || DEFAULT_EXCHANGE).toLowerCase();
  const adapter = REGISTRY[key];
  if (!adapter) {
    console.error(
      `[exchanges] San "${name}" khong duoc ho tro (chi co: ${Object.keys(REGISTRY).join(', ')}). ` +
        `Fallback ve "${DEFAULT_EXCHANGE}".`
    );
    return REGISTRY[DEFAULT_EXCHANGE];
  }
  return adapter;
}

module.exports = {
  getExchangeAdapter,
  SUPPORTED_EXCHANGES: Object.keys(REGISTRY),
  DEFAULT_EXCHANGE,
};
