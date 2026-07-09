'use strict';

const BINANCE_REST_BASE_URL = 'https://api.binance.com';

/**
 * Lay du lieu klines lich su tu Binance REST API de bootstrap.
 *
 * GET /api/v3/klines?symbol=...&interval=...&limit=...
 *
 * @param {Object} options
 * @param {string} options.symbol - vd "BTCUSDT"
 * @param {string} options.interval - vd "1m"
 * @param {number} [options.limit=500] - so luong nen toi da (Binance cho phep toi da 1000)
 * @returns {Promise<Array>} mang cac kline tho (array-of-arrays) tu Binance
 */
async function fetchKlines({ symbol, interval, limit = 500 }) {
  if (!symbol || !interval) {
    throw new Error('fetchKlines: thieu tham so bat buoc symbol/interval.');
  }

  const url = new URL('/api/v3/klines', BINANCE_REST_BASE_URL);
  url.searchParams.set('symbol', symbol.toUpperCase());
  url.searchParams.set('interval', interval);
  url.searchParams.set('limit', String(limit));

  try {
    const response = await fetch(url.toString(), { method: 'GET' });

    if (!response.ok) {
      const bodyText = await response.text().catch(() => '');
      throw new Error(
        `Binance REST tra ve loi HTTP ${response.status} ${response.statusText}: ${bodyText}`
      );
    }

    const data = await response.json();

    if (!Array.isArray(data)) {
      throw new Error('Binance REST tra ve du lieu khong dung dinh dang mang.');
    }

    return data;
  } catch (err) {
    console.error(
      `[binanceRest] Loi khi fetch klines lich su cho ${symbol} ${interval}:`,
      err.message
    );
    // Khong throw de tranh crash toan bo process — tra ve mang rong,
    // caller (index.js) se quyet dinh co retry hay khong.
    return [];
  }
}

module.exports = {
  fetchKlines,
  BINANCE_REST_BASE_URL,
};
