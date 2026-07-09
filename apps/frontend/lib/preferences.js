// preferences.js
// Lưu/đọc lựa chọn "filter" của người dùng (symbol + khung thời gian) vào
// localStorage để phiên sau khôi phục đúng thứ đang xem. Bọc try/catch vì
// localStorage có thể không dùng được (chế độ ẩn danh, bị chặn quyền, quota
// đầy) — khi đó im lặng bỏ qua, coi như "chưa lưu gì" và dùng mặc định.

const STORAGE_KEY = "cpc:filter"; // crypto-predictor-chart

// Chỉ chấp nhận các interval hợp lệ (khớp timeframeSelector.js) — tránh khôi
// phục một giá trị rác/cũ khiến API klines lỗi.
const VALID_INTERVALS = new Set(["1m", "1h", "1d", "1w", "1M"]);
const VALID_MARKETS = new Set(["crypto", "hose"]);

/**
 * Đọc filter đã lưu.
 * @returns {{ symbol: string, interval: string, market: string } | null}
 *   null nếu chưa lưu / dữ liệu không hợp lệ (caller dùng mặc định).
 */
export function loadFilter() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return null;

    const parsed = JSON.parse(raw);
    const symbol = typeof parsed?.symbol === "string" ? parsed.symbol : null;
    const interval = VALID_INTERVALS.has(parsed?.interval) ? parsed.interval : null;
    // market tuỳ chọn (tương thích bản lưu cũ chưa có market) -> mặc định crypto.
    const market = VALID_MARKETS.has(parsed?.market) ? parsed.market : "crypto";

    if (!symbol || !interval) return null;
    return { symbol, interval, market };
  } catch {
    return null;
  }
}

/**
 * Lưu filter hiện tại. Gọi mỗi khi người dùng đổi symbol/khung/thị trường.
 */
export function saveFilter(symbol, interval, market = "crypto") {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify({ symbol, interval, market }));
  } catch {
    // localStorage không dùng được -> bỏ qua, không làm gián đoạn UI.
  }
}
