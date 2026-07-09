// apiClient.js
// REST client cho api-gateway, theo contract định nghĩa trong
// packages/api-contracts/openapi.yaml:
//   GET /api/v1/klines?symbol=&interval=&limit=
//   GET /api/v1/predictions/latest?symbol=&interval=
//   GET /api/v1/accuracy?symbol=&range=
//   GET /api/v1/symbols
//
// Không có mock/dữ liệu giả lập nào ở đây — fetch lỗi sẽ ném lỗi thẳng lên
// caller (main.js) để hiển thị banner lỗi cho người dùng.

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8080";

async function fetchJson(path, params) {
  const url = new URL(path, API_BASE_URL);
  if (params) {
    Object.entries(params).forEach(([key, value]) => {
      if (value !== undefined && value !== null) {
        url.searchParams.set(key, value);
      }
    });
  }

  const response = await fetch(url.toString());
  if (!response.ok) {
    throw new Error(`Request failed: ${response.status} ${response.statusText}`);
  }
  return response.json();
}

/**
 * Lấy lịch sử nến.
 * GET /api/v1/klines?symbol=&interval=&limit=
 */
export function getKlines(symbol, interval, limit = 500) {
  return fetchJson("/api/v1/klines", { symbol, interval, limit });
}

/**
 * Lấy dự đoán nến tiếp theo.
 * GET /api/v1/predictions/latest?symbol=&interval=
 */
export function getLatestPrediction(symbol, interval) {
  return fetchJson("/api/v1/predictions/latest", { symbol, interval });
}

/**
 * Thống kê độ chính xác. "interval" optional — không truyền sẽ gộp accuracy
 * của mọi khung thời gian cùng symbol (xem packages/api-contracts/openapi.yaml).
 * GET /api/v1/accuracy?symbol=&range=&interval=
 */
export function getAccuracy(symbol, range = "24h", interval) {
  return fetchJson("/api/v1/accuracy", { symbol, range, interval });
}

/**
 * Danh sách symbol hỗ trợ. `market` tuỳ chọn ("hose" cho chứng khoán VN);
 * không truyền -> danh sách crypto (hành vi cũ).
 * GET /api/v1/symbols[?market=]
 */
export function getSymbols(market) {
  return fetchJson("/api/v1/symbols", market ? { market } : undefined);
}
