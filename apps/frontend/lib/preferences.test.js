import { beforeEach, afterEach, describe, expect, it, vi } from "vitest";
import { loadFilter, saveFilter } from "./preferences.js";

const STORAGE_KEY = "cpc:filter";

describe("preferences (lưu/đọc filter localStorage)", () => {
  beforeEach(() => {
    localStorage.clear();
    vi.restoreAllMocks();
  });
  afterEach(() => localStorage.clear());

  it("trả null khi chưa lưu gì", () => {
    expect(loadFilter()).toBeNull();
  });

  it("save + load khôi phục symbol/interval/market", () => {
    saveFilter("FPT", "1d", "hose");
    expect(loadFilter()).toEqual({ symbol: "FPT", interval: "1d", market: "hose" });
  });

  it("mặc định market=crypto khi không truyền", () => {
    saveFilter("ETHUSDT", "1h");
    expect(loadFilter()).toEqual({ symbol: "ETHUSDT", interval: "1h", market: "crypto" });
  });

  it("bản lưu cũ không có market -> crypto", () => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify({ symbol: "BTCUSDT", interval: "1d" }));
    expect(loadFilter().market).toBe("crypto");
  });

  it("market không hợp lệ -> crypto", () => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify({ symbol: "BTCUSDT", interval: "1d", market: "nasdaq" }));
    expect(loadFilter().market).toBe("crypto");
  });

  it("interval không hợp lệ -> null", () => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify({ symbol: "BTCUSDT", interval: "99x" }));
    expect(loadFilter()).toBeNull();
  });

  it("thiếu symbol -> null", () => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify({ interval: "1d" }));
    expect(loadFilter()).toBeNull();
  });

  it("JSON hỏng -> null (không crash)", () => {
    localStorage.setItem(STORAGE_KEY, "{khong-phai-json");
    expect(loadFilter()).toBeNull();
  });

  it("phân biệt 1m (phút) và 1M (tháng)", () => {
    saveFilter("BTCUSDT", "1M");
    expect(loadFilter().interval).toBe("1M");
    saveFilter("BTCUSDT", "1m");
    expect(loadFilter().interval).toBe("1m");
  });

  it("saveFilter không ném lỗi khi setItem thất bại", () => {
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
      throw new Error("Quota");
    });
    expect(() => saveFilter("BTCUSDT", "1d")).not.toThrow();
  });
});
