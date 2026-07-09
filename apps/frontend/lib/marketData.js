// marketData.js
// Nguồn dữ liệu dùng chung cho ticker tape + market list widget. KHÔNG có
// mock/dữ liệu giả — lấy giá gần nhất + % thay đổi so với nến trước đó bằng
// GET /api/v1/klines?limit=2 (2 nến gần nhất) cho từng symbol thật.
//
// Lưu ý: đây là % thay đổi so với NẾN TRƯỚC (1 phút gần nhất với interval
// mặc định), không phải % thay đổi 24h — backend hiện chưa có endpoint tổng
// hợp 24h nên không suy diễn số liệu không có thật.

import { getKlines } from "./apiClient.js";

/**
 * @param {string} symbol
 * @param {string} interval - khung để lấy 2 nến gần nhất (crypto "1m", HOSE "1d").
 */
async function fetchSymbolSnapshot(symbol, interval) {
  const klines = await getKlines(symbol, interval, 2);
  if (!Array.isArray(klines) || klines.length === 0) return null;

  const latest = klines[0];
  const previous = klines[1];

  const price = Number(latest.close);
  const changePct = previous ? ((price - Number(previous.close)) / Number(previous.close)) * 100 : null;

  return { symbol, price, changePct };
}

/**
 * Lấy snapshot giá cho danh sách symbol, bỏ qua symbol lỗi.
 * @param {string[]} symbols
 * @param {string} interval - mặc định "1m" (crypto); truyền "1d" cho HOSE.
 */
export async function fetchMarketSnapshot(symbols, interval = "1m") {
  const results = await Promise.all(
    symbols.map((symbol) =>
      fetchSymbolSnapshot(symbol, interval).catch((err) => {
        console.warn(`[marketData] Không lấy được snapshot cho ${symbol}`, err);
        return null;
      })
    )
  );
  return results.filter(Boolean);
}
