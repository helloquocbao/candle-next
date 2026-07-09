import { describe, it, expect, vi } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import MarketList from "./MarketList";

// Mock nguồn data (không gọi mạng thật trong test).
vi.mock("../lib/marketData.js", () => ({
  fetchMarketSnapshot: vi.fn(async () => [
    { symbol: "FPT", price: 72.5, changePct: 1.2 },
    { symbol: "VNM", price: 55.8, changePct: -0.5 },
  ]),
}));

describe("MarketList", () => {
  it("render các dòng symbol và gọi onSelect khi click", async () => {
    const onSelect = vi.fn();
    render(
      <MarketList symbols={["FPT", "VNM"]} interval="1d" activeSymbol="FPT" onSelect={onSelect} />
    );

    await waitFor(() => expect(screen.getByText("FPT")).toBeInTheDocument());
    expect(screen.getByText("VNM")).toBeInTheDocument();
    // Giá + % được format.
    expect(screen.getByText("72.50")).toBeInTheDocument();
    expect(screen.getByText("+1.20%")).toBeInTheDocument();

    fireEvent.click(screen.getByText("VNM"));
    expect(onSelect).toHaveBeenCalledWith("VNM");
  });
});
