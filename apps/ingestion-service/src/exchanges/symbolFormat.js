'use strict';

/**
 * Chuyen doi symbol/interval tu format CHUAN NOI BO (theo quy uoc Binance:
 * symbol "BTCUSDT", interval "1m"/"1h"/"1d"/"1w"/"1M") sang format rieng cua
 * tung san (OKX, Bybit). Giu format Binance lam chuan de khong phai doi
 * downstream (DB/Redis/prediction-engine deu key theo symbol+interval nay).
 *
 * Thuan (pure) - de test doc lap, khong I/O.
 */

// Cac quote asset thuong gap, sap xep DAI -> NGAN de match dung suffix (vd
// "BTCUSDT" phai tach thanh BTC+USDT, khong phai BTC+USD... de lai "T").
const KNOWN_QUOTE_ASSETS = [
  'FDUSD',
  'USDT',
  'USDC',
  'TUSD',
  'BUSD',
  'DAI',
  'USD',
  'BTC',
  'ETH',
  'BNB',
  'EUR',
  'TRY',
  'BRL',
  'SOL',
].sort((a, b) => b.length - a.length);

/**
 * Tach symbol chuan (vd "BTCUSDT") thanh { base, quote } dua tren danh sach
 * quote asset pho bien. Tra ve null neu khong nhan dien duoc quote.
 */
function splitSymbol(symbol) {
  const upper = String(symbol).toUpperCase();
  for (const quote of KNOWN_QUOTE_ASSETS) {
    if (upper.length > quote.length && upper.endsWith(quote)) {
      return { base: upper.slice(0, upper.length - quote.length), quote };
    }
  }
  return null;
}

/**
 * Phan tich interval chuan Binance thanh { amount, unit }.
 * QUAN TRONG: phan biet HOA/thuong — "m" = phut, "M" = thang (dung quy uoc
 * Binance, xem prediction-engine main.py::_interval_to_timedelta).
 */
function parseInterval(interval) {
  const match = /^(\d+)([mhdwM])$/.exec(String(interval));
  if (!match) {
    throw new Error(`Interval khong hop le "${interval}" (dinh dang dung: 1m, 5m, 1h, 1d, 1w, 1M).`);
  }
  return { amount: Number(match[1]), unit: match[2] };
}

// ---------------------------------------------------------------- OKX ----

/**
 * "BTCUSDT" -> "BTC-USDT" (spot). instType SWAP se la "BTC-USDT-SWAP" nhung
 * mac dinh ta dung SPOT de dong bo voi Binance spot hien tai.
 */
function toOkxInstId(symbol) {
  const parts = splitSymbol(symbol);
  if (!parts) {
    throw new Error(`Khong tach duoc quote asset tu symbol "${symbol}" cho OKX.`);
  }
  return `${parts.base}-${parts.quote}`;
}

/**
 * Interval chuan -> OKX "bar": phut giu chu thuong (1m), gio/ngay/tuan/thang
 * viet HOA (1H, 1D, 1W, 1M). Vd: "1h" -> "1H", "1m" -> "1m", "1M" -> "1M".
 */
function toOkxBar(interval) {
  const { amount, unit } = parseInterval(interval);
  const OKX_UNIT = { m: 'm', h: 'H', d: 'D', w: 'W', M: 'M' };
  return `${amount}${OKX_UNIT[unit]}`;
}

// -------------------------------------------------------------- Bybit ----

/**
 * Bybit v5 giu nguyen symbol dang "BTCUSDT" (giong Binance) -> khong doi.
 */
function toBybitSymbol(symbol) {
  return String(symbol).toUpperCase();
}

/**
 * Interval chuan -> Bybit v5 "interval": phut/gio quy ve SO PHUT dang chuoi
 * (1m->"1", 1h->"60", 4h->"240"); ngay/tuan/thang la "D"/"W"/"M".
 */
function toBybitInterval(interval) {
  const { amount, unit } = parseInterval(interval);
  if (unit === 'm') return String(amount);
  if (unit === 'h') return String(amount * 60);
  if (unit === 'd') return 'D';
  if (unit === 'w') return 'W';
  if (unit === 'M') return 'M';
  throw new Error(`Interval "${interval}" khong ho tro cho Bybit.`);
}

module.exports = {
  KNOWN_QUOTE_ASSETS,
  splitSymbol,
  parseInterval,
  toOkxInstId,
  toOkxBar,
  toBybitSymbol,
  toBybitInterval,
};
