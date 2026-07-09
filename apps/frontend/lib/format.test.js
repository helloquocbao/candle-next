import { describe, expect, it } from "vitest";
import { formatPrice, formatChange, directionOf } from "./format.js";

describe("format helpers", () => {
  it("formatPrice 2 chữ số thập phân", () => {
    expect(formatPrice(62500)).toBe("62,500.00");
    expect(formatPrice(1.5)).toBe("1.50");
  });

  it("formatChange có dấu + khi tăng, -- khi null/NaN", () => {
    expect(formatChange(2.415)).toBe("+2.42%");
    expect(formatChange(-1.2)).toBe("-1.20%");
    expect(formatChange(null)).toBe("--");
    expect(formatChange(NaN)).toBe("--");
  });

  it("directionOf phân loại up/down/flat", () => {
    expect(directionOf(1)).toBe("up");
    expect(directionOf(-1)).toBe("down");
    expect(directionOf(0)).toBe("flat");
    expect(directionOf(null)).toBe("flat");
  });
});
