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

const VALID_HOSE_SYMBOLS = new Set(["FPT", "VNM", "VIC", "HPG", "MWG", "VCB", "PNJ"]);

export function loadFilter() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return null;

    const parsed = JSON.parse(raw);
    let symbol = typeof parsed?.symbol === "string" ? parsed.symbol.toUpperCase() : "FPT";
    if (!VALID_HOSE_SYMBOLS.has(symbol)) {
      symbol = "FPT";
    }
    const interval = "1d";
    const market = "hose";

    return { symbol, interval, market };
  } catch {
    return null;
  }
}

/**
 * Lưu filter hiện tại. Gọi mỗi khi người dùng đổi symbol/khung/thị trường.
 */
export function saveFilter(symbol, interval, market = "hose") {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify({ symbol, interval, market: "hose" }));
  } catch {
    // localStorage không dùng được -> bỏ qua, không làm gián đoạn UI.
  }
}

