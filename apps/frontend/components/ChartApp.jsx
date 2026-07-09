"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import { createChartRenderer } from "../lib/chartRenderer.js";
import { getKlines, getSymbols, getAccuracy, getLatestPrediction } from "../lib/apiClient.js";
import { wsClient } from "../lib/wsClient.js";
import { loadFilter, saveFilter } from "../lib/preferences.js";
import TickerTape from "./TickerTape";
import MarketList from "./MarketList";

const DEFAULT_SYMBOL = "BTCUSDT";
const DEFAULT_INTERVAL = "1d";
const KLINES_LIMIT = 200;
const HOSE_INTERVAL = "1d";
const LONG_HORIZON = new Set(["1d", "1w", "1M"]);
const ACCURACY_RANGE = "3650d";
const TIMEFRAMES = [
  { interval: "1m", label: "1m" },
  { interval: "1h", label: "1H" },
  { interval: "1d", label: "1D" },
  { interval: "1w", label: "1W" },
  { interval: "1M", label: "1M" },
];
const WALLETS = [
  { net: "BTC", addr: "bc1qexample…exampl0", full: "bc1qexampleexampleexampleexampleexampl0" },
  { net: "ETH / USDT (ERC-20)", addr: "0xExample…Exa00", full: "0xExampleExampleExampleExampleExampleExa00" },
  { net: "USDT (TRC-20)", addr: "TExample…T0", full: "TExampleExampleExampleExampleExampleT0" },
];

const STATUS_LABEL = {
  connecting: "Đang kết nối...",
  connected: "Đã kết nối",
  disconnected: "Mất kết nối, đang thử lại...",
  error: "Lỗi kết nối",
};

export default function ChartApp() {
  const containerRef = useRef(null);
  const rendererRef = useRef(null);
  // Ref theo dõi cặp/thị trường hiện tại cho handler WS (tránh stale closure).
  const currentRef = useRef({ symbol: DEFAULT_SYMBOL, interval: DEFAULT_INTERVAL, market: "crypto" });

  const [market, setMarket] = useState("crypto");
  const [symbol, setSymbol] = useState(DEFAULT_SYMBOL);
  const [interval, setIntervalState] = useState(DEFAULT_INTERVAL);
  const [symbols, setSymbols] = useState(["BTCUSDT", "ETHUSDT", "SOLUSDT"]);
  const [status, setStatus] = useState("connecting");
  const [accuracy, setAccuracy] = useState("--%");
  const [error, setError] = useState("");
  const [copied, setCopied] = useState(-1);

  const allowedIntervals = market === "hose" ? new Set([HOSE_INTERVAL]) : null;
  const snapInterval = market === "hose" ? "1d" : "1m";

  const loadHistoryAndRender = useCallback(async (sym, intv) => {
    const r = rendererRef.current;
    if (!r) return;
    try {
      const klines = await getKlines(sym, intv, KLINES_LIMIT);
      r.setRealData(klines);
      r.clearForecastZone();
      r.setForecastStyleForInterval(intv);
      setError("");
    } catch (err) {
      setError(`Không thể tải dữ liệu nến cho ${sym}: ${err.message}`);
      return;
    }
    try {
      const latest = await getLatestPrediction(sym, intv);
      if (Array.isArray(latest.predictions) && latest.predictions.length > 0) {
        r.updateForecastZone(latest.predictions);
      }
    } catch {
      /* seed dự đoán thất bại -> chờ WS, không chặn */
    }
    r.clearAccuracyMarkers();
    if (LONG_HORIZON.has(intv)) {
      try {
        const res = await getAccuracy(sym, ACCURACY_RANGE, intv);
        r.setAccuracyMarkers(res.samples || []);
      } catch {
        /* bỏ qua */
      }
    }
  }, []);

  const switchTo = useCallback(
    (newSymbol, newInterval, newMarket) => {
      const prev = currentRef.current;
      if (newSymbol === prev.symbol && newInterval === prev.interval && newMarket === prev.market) return;

      wsClient.unsubscribe(prev.symbol, prev.interval);
      currentRef.current = { symbol: newSymbol, interval: newInterval, market: newMarket };
      setSymbol(newSymbol);
      setIntervalState(newInterval);
      setMarket(newMarket);
      setAccuracy("--%");
      saveFilter(newSymbol, newInterval, newMarket);

      loadHistoryAndRender(newSymbol, newInterval).then(() => {
        wsClient.subscribe(newSymbol, newInterval);
      });
    },
    [loadHistoryAndRender]
  );

  const onSelectSymbol = (e) => switchTo(e.target.value, currentRef.current.interval, currentRef.current.market);
  const onSelectInterval = (intv) => {
    if (allowedIntervals && !allowedIntervals.has(intv)) return;
    switchTo(currentRef.current.symbol, intv, currentRef.current.market);
  };

  const onSwitchMarket = async (newMarket) => {
    if (newMarket === currentRef.current.market) return;
    let list;
    try {
      list = await getSymbols(newMarket === "hose" ? "hose" : undefined);
    } catch {
      list = [];
    }
    if (!Array.isArray(list) || list.length === 0) {
      setError(`Chưa có dữ liệu cho thị trường "${newMarket}".`);
      return;
    }
    setSymbols(list);
    const cur = currentRef.current;
    const newSymbol = list.includes(cur.symbol) ? cur.symbol : list[0];
    const newInterval = newMarket === "hose" ? HOSE_INTERVAL : cur.interval;
    switchTo(newSymbol, newInterval, newMarket);
  };

  const copyWallet = async (i) => {
    try {
      await navigator.clipboard.writeText(WALLETS[i].full);
      setCopied(i);
      setTimeout(() => setCopied(-1), 1600);
    } catch {
      /* bỏ qua */
    }
  };

  // Khởi tạo 1 lần: chart + WS + load lần đầu.
  useEffect(() => {
    const saved = loadFilter();
    const initMarket = saved?.market || "crypto";
    const initSymbol = saved?.symbol || DEFAULT_SYMBOL;
    const initInterval = saved?.interval || DEFAULT_INTERVAL;
    currentRef.current = { symbol: initSymbol, interval: initInterval, market: initMarket };
    setMarket(initMarket);
    setSymbol(initSymbol);
    setIntervalState(initInterval);

    rendererRef.current = createChartRenderer(containerRef.current);

    wsClient.onMessage("status", (s) => setStatus(s));
    wsClient.onMessage("kline", (data) => {
      if (!data || data.symbol !== currentRef.current.symbol) return;
      rendererRef.current?.updateRealCandle(data);
    });
    wsClient.onMessage("prediction", (data) => {
      if (!data || data.symbol !== currentRef.current.symbol) return;
      if (!Array.isArray(data.predictions)) return;
      rendererRef.current?.updateForecastZone(data.predictions);
    });
    wsClient.onMessage("accuracy_update", (data) => {
      if (!data) return;
      if (data.symbol && data.symbol !== currentRef.current.symbol) return;
      if (typeof data.accuracy_pct === "number") setAccuracy(`${data.accuracy_pct.toFixed(1)}%`);
      if (LONG_HORIZON.has(currentRef.current.interval) && data.open_time) {
        rendererRef.current?.addAccuracyMarker(data);
      }
    });

    // Nạp symbols theo thị trường + load lịch sử ban đầu.
    (async () => {
      try {
        const list = await getSymbols(initMarket === "hose" ? "hose" : undefined);
        if (Array.isArray(list) && list.length > 0) {
          setSymbols(list);
          if (!list.includes(initSymbol)) {
            currentRef.current.symbol = list[0];
            setSymbol(list[0]);
          }
        }
      } catch {
        /* dùng fallback */
      }
      await loadHistoryAndRender(currentRef.current.symbol, currentRef.current.interval);
      wsClient.connect();
      wsClient.onMessage("status", (s) => {
        if (s === "connected") wsClient.subscribe(currentRef.current.symbol, currentRef.current.interval);
      });
    })();

    return () => {
      try {
        rendererRef.current?.destroy();
      } catch {
        /* bỏ qua */
      }
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div id="app">
      <header className="site-header">
        <a className="brand" href="/">
          <span className="brand-mark">Cp</span>
          <span>CryptoPredict</span>
        </a>
        <nav className="main-nav" aria-label="Điều hướng chính">
          <a href="/">Trang chủ</a>
          <a href="/app" aria-current="page">Biểu đồ</a>
        </nav>
        <div className="header-actions">
          <span className="connection-status" data-status={status}>{STATUS_LABEL[status] || status}</span>
          {/* ThemeToggle client — import động để tránh vòng phụ thuộc */}
          <ThemeToggleInline />
        </div>
      </header>

      <TickerTape symbols={symbols} interval={snapInterval} />

      <div className="portal-layout">
        <main className="card chart-card">
          <div className="chart-toolbar">
            <div className="market-toggle" role="group" aria-label="Thị trường">
              <button type="button" className="market-btn" data-active={String(market === "crypto")} onClick={() => onSwitchMarket("crypto")}>Crypto</button>
              <button type="button" className="market-btn" data-active={String(market === "hose")} onClick={() => onSwitchMarket("hose")}>CK VN</button>
            </div>
            <label htmlFor="symbol-selector" className="control-label">Symbol</label>
            <select id="symbol-selector" className="symbol-selector" value={symbol} onChange={onSelectSymbol}>
              {symbols.map((s) => (<option key={s} value={s}>{s}</option>))}
            </select>
            <div className="timeframe-selector" role="group" aria-label="Khung thời gian">
              {TIMEFRAMES.map(({ interval: tf, label }) => {
                const disabled = allowedIntervals ? !allowedIntervals.has(tf) : false;
                return (
                  <button key={tf} type="button" className="timeframe-btn"
                    data-active={String(tf === interval)} data-disabled={String(disabled)}
                    disabled={disabled} onClick={() => onSelectInterval(tf)}>
                    {label}
                  </button>
                );
              })}
            </div>
            <div className="accuracy-wrapper">
              <span className="accuracy-label">Độ chính xác:</span>
              <span className="accuracy-badge">{accuracy}</span>
            </div>
          </div>

          {error ? <div className="error-banner">{error}</div> : null}

          <div className="chart-body">
            <div id="chart-container" ref={containerRef} />
          </div>

          <p className="chart-disclaimer" role="note">
            ⚠️ Vùng nến tương lai là dự đoán do thuật toán tạo ra, chỉ mang tính tham khảo &amp;
            thử nghiệm — <strong>không phải lời khuyên đầu tư</strong>. Bạn tự chịu trách nhiệm cho
            mọi quyết định giao dịch.
          </p>
        </main>

        <aside className="sidebar">
          <div className="card donate-card">
            <p className="widget-title">Ủng hộ dự án</p>
            <p className="donate-desc">
              CryptoPredict miễn phí và không gọi vốn. Nếu thấy hữu ích, bạn có thể ủng hộ tự
              nguyện để duy trì máy chủ.
            </p>
            {/* TODO: thay YOUR_HANDLE bằng username Buy Me a Coffee thật. */}
            <a className="donate-bmc" href="https://www.buymeacoffee.com/YOUR_HANDLE" target="_blank" rel="noopener noreferrer">☕ Buy me a coffee</a>
            <p className="donate-wallets__title">Hoặc ủng hộ bằng ví crypto:</p>
            {WALLETS.map((w, i) => (
              <button key={w.net} className="donate-wallet" type="button" onClick={() => copyWallet(i)}>
                <span className="donate-wallet__net">{w.net}</span>
                <span className="donate-wallet__addr">{w.addr}</span>
                <span className="donate-wallet__copy">{copied === i ? "Đã sao chép ✓" : "Sao chép"}</span>
              </button>
            ))}
          </div>

          <div className="ad-slot ad-slot--rectangle" role="complementary" aria-label="Quảng cáo">
            <span className="ad-slot__label">Quảng cáo</span>
            <span className="ad-slot__size">300 × 250</span>
          </div>

          <div className="card">
            <p className="widget-title">Thị trường</p>
            <MarketList
              symbols={symbols}
              interval={snapInterval}
              activeSymbol={symbol}
              onSelect={(s) => switchTo(s, currentRef.current.interval, currentRef.current.market)}
            />
          </div>
        </aside>
      </div>
    </div>
  );
}

// Nhúng ThemeToggle trực tiếp để tránh thêm file import ở header.
function ThemeToggleInline() {
  const [theme, setTheme] = useState("light");
  useEffect(() => {
    try {
      setTheme(localStorage.getItem("theme") === "dark" ? "dark" : "light");
    } catch { /* bỏ qua */ }
  }, []);
  useEffect(() => {
    if (theme === "dark") document.documentElement.setAttribute("data-theme", "dark");
    else document.documentElement.removeAttribute("data-theme");
  }, [theme]);
  return (
    <button className="theme-toggle" type="button"
      aria-label={theme === "dark" ? "Chuyển sang giao diện sáng" : "Chuyển sang giao diện tối"}
      onClick={() => {
        const t = theme === "dark" ? "light" : "dark";
        try { localStorage.setItem("theme", t); } catch { /* bỏ qua */ }
        setTheme(t);
      }}>
      {theme === "dark" ? "☀️" : "🌙"}
    </button>
  );
}
