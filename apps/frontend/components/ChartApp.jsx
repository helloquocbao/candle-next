"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import { createChartRenderer } from "../lib/chartRenderer.js";
import { getKlines, getSymbols, getAccuracy, getLatestPrediction } from "../lib/apiClient.js";
import { wsClient } from "../lib/wsClient.js";
import { loadFilter, saveFilter } from "../lib/preferences.js";
import TickerTape from "./TickerTape";
import MarketList from "./MarketList";

const DEFAULT_SYMBOL = "FPT";
const DEFAULT_INTERVAL = "1d";
const KLINES_LIMIT = 200;
const HOSE_INTERVAL = "1d";
const LONG_HORIZON = new Set(["1d", "1w", "1M"]);
const ACCURACY_RANGE = "3650d";
const TIMEFRAMES = [
  { interval: "1d", label: "1D" },
  { interval: "1w", label: "1W" },
  { interval: "1M", label: "1M" },
];
const WALLETS = [];

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
  const currentRef = useRef({ symbol: DEFAULT_SYMBOL, interval: DEFAULT_INTERVAL, market: "hose" });

  const [market, setMarket] = useState("hose");
  const [symbol, setSymbol] = useState(DEFAULT_SYMBOL);
  const [interval, setIntervalState] = useState(DEFAULT_INTERVAL);
  const [symbols, setSymbols] = useState(["FPT", "VNM", "VIC", "HPG", "MWG", "VCB"]);
  const [status, setStatus] = useState("connecting");
  const [accuracy, setAccuracy] = useState("--%");
  const [error, setError] = useState("");
  const [copied, setCopied] = useState(-1);

  const isSimulatingRef = useRef(false);
  const simTargetRef = useRef(5.0);
  const simStopRef = useRef(2.5);
  const simStepsRef = useRef(5);

  const [isSimulating, setIsSimulating] = useState(false);
  const [simTarget, setSimTarget] = useState(5.0);
  const [simStop, setSimStop] = useState(2.5);
  const [simSteps, setSimSteps] = useState(5);

  useEffect(() => {
    isSimulatingRef.current = isSimulating;
    simTargetRef.current = simTarget;
    simStopRef.current = simStop;
    simStepsRef.current = simSteps;
  }, [isSimulating, simTarget, simStop, simSteps]);

  const calculateAndApplySimulation = useCallback((targetVal, stopVal, stepsVal) => {
    const r = rendererRef.current;
    if (!r) return;
    const refClose = latestCloseRef.current || 100.0;
    const targetPct = Number(targetVal);
    const stopPct = Number(stopVal);
    const steps = Number(stepsVal);
    
    const simulated = [];
    for (let step = 1; step <= steps; step++) {
      const targetTime = new Date();
      targetTime.setDate(targetTime.getDate() + step);
      
      simulated.push({
        step,
        target_time: targetTime.toISOString().split("T")[0],
        predicted_open: refClose,
        predicted_high: refClose * (1.0 + targetPct / 100.0),
        predicted_low: refClose * (1.0 - stopPct / 100.0),
        predicted_close: refClose * (1.0 + targetPct / 100.0),
      });
    }
    r.updateForecastZone(simulated, true);
  }, []);

  useEffect(() => {
    if (isSimulating) {
      calculateAndApplySimulation(simTarget, simStop, simSteps);
    }
  }, [isSimulating, simTarget, simStop, simSteps, calculateAndApplySimulation]);

  const handleToggleSimulation = (e) => {
    const val = e.target.checked;
    setIsSimulating(val);
    if (!val) {
      getLatestPrediction(symbol, interval)
        .then((latest) => {
          if (Array.isArray(latest.predictions) && latest.predictions.length > 0) {
            rendererRef.current?.updateForecastZone(latest.predictions);
          } else {
            rendererRef.current?.clearForecastZone();
          }
        })
        .catch(() => {
          rendererRef.current?.clearForecastZone();
        });
    }
  };

  const latestCloseRef = useRef(0);
  const allowedIntervals = market === "hose" ? new Set(["1d", "1w", "1M"]) : null;
  const snapInterval = market === "hose" ? "1d" : "1m";

  const loadHistoryAndRender = useCallback(async (sym, intv) => {
    const r = rendererRef.current;
    if (!r) return;
    try {
      const klines = await getKlines(sym, intv, KLINES_LIMIT);
      r.setRealData(klines);
      if (klines && klines.length > 0) {
        latestCloseRef.current = Number(klines[klines.length - 1].close);
      }
      r.clearForecastZone();
      r.setForecastStyleForInterval(intv);
      setError("");
    } catch (err) {
      setError(`Không thể tải dữ liệu nến cho ${sym}: ${err.message}`);
      return;
    }
    if (isSimulatingRef.current) {
      calculateAndApplySimulation(simTargetRef.current, simStopRef.current, simStepsRef.current);
    } else {
      try {
        let latest = { predictions: [] };
        if (intv === "1w") {
          try {
            const dailyPreds = await getLatestPrediction(sym, "1d");
            if (Array.isArray(dailyPreds.predictions) && dailyPreds.predictions.length > 0) {
              const sorted = [...dailyPreds.predictions].sort((a, b) => a.step - b.step);
              const first = sorted[0];
              const last = sorted[sorted.length - 1];
              const high = Math.max(...sorted.map(p => Number(p.predicted_high)));
              const low = Math.min(...sorted.map(p => Number(p.predicted_low)));
              latest = {
                predictions: [{
                  step: 1,
                  target_time: last.target_time,
                  predicted_open: Number(first.predicted_open),
                  predicted_high: high,
                  predicted_low: low,
                  predicted_close: Number(last.predicted_close),
                  confidence: Number(first.confidence),
                  model_version: "aggregated-1w",
                }]
              };
            }
          } catch (e) {
            console.error("Failed to aggregate weekly prediction:", e);
          }
        } else if (intv === "1M") {
          try {
            const history = await getKlines(sym, "1M", 20);
            if (history && history.length >= 2) {
              const sortedHistory = [...history].sort((a, b) => new Date(a.open_time) - new Date(b.open_time));
              const lastKline = sortedHistory[sortedHistory.length - 1];
              const refClose = Number(lastKline.close);
              const closes = sortedHistory.map(k => Number(k.close));
              const returns = [];
              for (let i = 1; i < closes.length; i++) {
                if (closes[i-1] > 0) returns.push(closes[i] / closes[i-1] - 1.0);
              }
              let drift = 0.0;
              if (returns.length > 0) {
                const span = 10;
                const alpha = 2.0 / (span + 1.0);
                drift = returns[0];
                for (let i = 1; i < returns.length; i++) {
                  drift = alpha * returns[i] + (1.0 - alpha) * drift;
                }
              }
              const ranges = sortedHistory.map(k => Number(k.high) - Number(k.low));
              const atr = ranges.reduce((s, r) => s + r, 0) / ranges.length;

              const predictedOpen = refClose;
              const predictedClose = refClose * (1.0 + drift);
              const halfRange = atr / 2.0;
              const predictedHigh = Math.max(predictedOpen, predictedClose) + halfRange;
              const predictedLow = Math.min(predictedOpen, predictedClose) - halfRange;

              const targetTime = new Date();
              targetTime.setMonth(targetTime.getMonth() + 1);

              latest = {
                predictions: [{
                  step: 1,
                  target_time: targetTime.toISOString().split("T")[0],
                  predicted_open: predictedOpen,
                  predicted_high: predictedHigh,
                  predicted_low: predictedLow,
                  predicted_close: predictedClose,
                  confidence: 0.8,
                  model_version: "monthly-calc-1M",
                }]
              };
            }
          } catch (e) {
            console.error("Failed to calculate monthly prediction:", e);
          }
        } else {
          latest = await getLatestPrediction(sym, intv);
        }

        if (Array.isArray(latest.predictions) && latest.predictions.length > 0) {
          r.updateForecastZone(latest.predictions);
        }
      } catch {
        /* seed dự đoán thất bại -> chờ WS, không chặn */
      }
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
  }, [calculateAndApplySimulation]);

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
    const initMarket = "hose";
    const initSymbol = saved?.symbol || DEFAULT_SYMBOL;
    const initInterval = DEFAULT_INTERVAL;
    currentRef.current = { symbol: initSymbol, interval: initInterval, market: initMarket };
    setMarket(initMarket);
    setSymbol(initSymbol);
    setIntervalState(initInterval);

    rendererRef.current = createChartRenderer(containerRef.current);

    wsClient.onMessage("status", (s) => setStatus(s));
    wsClient.onMessage("kline", (data) => {
      if (!data || data.symbol !== currentRef.current.symbol) return;
      rendererRef.current?.updateRealCandle(data);
      latestCloseRef.current = Number(data.close);
      if (isSimulatingRef.current) {
        calculateAndApplySimulation(simTargetRef.current, simStopRef.current, simStepsRef.current);
      }
    });
    wsClient.onMessage("prediction", (data) => {
      if (isSimulatingRef.current) return;
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
          <span className="brand-mark">Hp</span>
          <span>HosePredict</span>
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
            <div className="market-toggle" role="group" aria-label="Thị trường" style={{ display: "none" }}>
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
          <div className="card simulation-card">
            <p className="widget-title">⚙️ Giả lập Vùng Dự Đoán</p>
            <p className="donate-desc">
              Tự định nghĩa các kịch bản xu hướng để đánh giá tình hình thị trường.
            </p>
            <div className="sim-control">
              <label className="sim-checkbox-label">
                <input
                  type="checkbox"
                  checked={isSimulating}
                  onChange={handleToggleSimulation}
                />
                <span>Kích hoạt Giả lập</span>
              </label>
            </div>
            
            {isSimulating && (
              <div className="sim-sliders">
                <div className="sim-slider-group">
                  <div className="sim-slider-header">
                    <span>Mục tiêu chốt lời (Target):</span>
                    <span className="sim-value">+{simTarget}%</span>
                  </div>
                  <input
                    type="range"
                    min="0.5"
                    max="20"
                    step="0.1"
                    value={simTarget}
                    onChange={(e) => setSimTarget(parseFloat(e.target.value))}
                    className="sim-slider"
                  />
                </div>
                
                <div className="sim-slider-group">
                  <div className="sim-slider-header">
                    <span>Biên giới hạn cắt lỗ (Stop):</span>
                    <span className="sim-value">-{simStop}%</span>
                  </div>
                  <input
                    type="range"
                    min="0.5"
                    max="15"
                    step="0.1"
                    value={simStop}
                    onChange={(e) => setSimStop(parseFloat(e.target.value))}
                    className="sim-slider"
                  />
                </div>
                
                <div className="sim-slider-group">
                  <div className="sim-slider-header">
                    <span>Số phiên (Steps):</span>
                    <span className="sim-value">{simSteps} phiên</span>
                  </div>
                  <input
                    type="range"
                    min="1"
                    max="15"
                    step="1"
                    value={simSteps}
                    onChange={(e) => setSimSteps(parseInt(e.target.value))}
                    className="sim-slider"
                  />
                </div>
              </div>
            )}
          </div>

          <div className="card donate-card">
            <p className="widget-title">Ủng hộ dự án</p>
            <p className="donate-desc">
              HosePredict miễn phí và không gọi vốn. Nếu thấy hữu ích, bạn có thể ủng hộ tự
              nguyện để duy trì máy chủ.
            </p>
            {/* TODO: thay YOUR_HANDLE bằng username Buy Me a Coffee thật. */}
            <a className="donate-bmc" href="https://www.buymeacoffee.com/YOUR_HANDLE" target="_blank" rel="noopener noreferrer">☕ Buy me a coffee</a>
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
