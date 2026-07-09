"use client";

import { useEffect, useState } from "react";
import { fetchMarketSnapshot } from "../lib/marketData.js";
import { formatPrice, formatChange, directionOf } from "../lib/format.js";

const REFRESH_MS = 20_000;

// Dải giá chạy ngang real-time cho các symbol của thị trường hiện tại.
export default function TickerTape({ symbols, interval }) {
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

  const doubled = snaps.length ? [...snaps, ...snaps] : [];

  return (
    <div className="ticker-tape" aria-label="Giá real-time các symbol">
      <div className="ticker-tape__track">
        {doubled.map((s, i) => (
          <span className="ticker-item" key={`${s.symbol}-${i}`}>
            <span className="ticker-item__symbol">{s.symbol}</span>
            <span className="ticker-item__price">{formatPrice(s.price)}</span>
            <span className="ticker-item__change" data-direction={directionOf(s.changePct)}>
              {formatChange(s.changePct)}
            </span>
          </span>
        ))}
      </div>
    </div>
  );
}
