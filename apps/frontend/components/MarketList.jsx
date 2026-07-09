"use client";

import { useEffect, useState } from "react";
import { fetchMarketSnapshot } from "../lib/marketData.js";
import { formatPrice, formatChange, directionOf } from "../lib/format.js";

const REFRESH_MS = 20_000;

// Danh sách giá các symbol trong sidebar; click 1 dòng -> đổi symbol chart.
export default function MarketList({ symbols, interval, activeSymbol, onSelect }) {
  const [snaps, setSnaps] = useState([]);

  useEffect(() => {
    let alive = true;
    async function refresh() {
      try {
        const s = await fetchMarketSnapshot(symbols, interval);
        if (alive) setSnaps(s);
      } catch {
        /* bỏ qua */
      }
    }
    refresh();
    const t = setInterval(refresh, REFRESH_MS);
    return () => {
      alive = false;
      clearInterval(t);
    };
  }, [symbols, interval]);

  return (
    <div className="market-list">
      {snaps.map((s) => (
        <a
          key={s.symbol}
          href="#"
          className="market-list__row"
          data-symbol={s.symbol}
          data-active={String(s.symbol === activeSymbol)}
          onClick={(e) => {
            e.preventDefault();
            onSelect(s.symbol);
          }}
        >
          <span className="market-list__symbol">{s.symbol}</span>
          <span className="market-list__meta">
            <span className="market-list__price">{formatPrice(s.price)}</span>
            <span className="market-list__change" data-direction={directionOf(s.changePct)}>
              {formatChange(s.changePct)}
            </span>
          </span>
        </a>
      ))}
    </div>
  );
}
