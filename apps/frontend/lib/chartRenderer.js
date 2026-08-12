// chartRenderer.js
// Khởi tạo TradingView Lightweight Charts:
//   - realSeries: nến thực (candlestick) từ dữ liệu klines
//   - forecast zone: 1 vùng giá dự đoán trong tương lai (canvas overlay vẽ
//     hình chữ nhật 2 màu tách bởi giá hiện tại — xanh phía trên/đỏ phía
//     dưới — kèm nhãn %, kiểu công cụ "Long/Short Position" của TradingView)
//     thay vì vẽ từng nến mờ riêng lẻ. Vùng này lấy min/max trên toàn bộ dải
//     multi-step forecast từ prediction-engine (xem
//     prediction-engine::predict_next_n_candles).

import { createChart, CrosshairMode } from "lightweight-charts";

// Khung ngày/tuần/tháng dự đoán vốn kém chắc chắn hơn 1m/1h -> vùng dự đoán
// vẽ mờ hơn hẳn để truyền đạt đúng mức độ không chắc chắn đó.
const ZONE_STYLES = {
  normal: { fill: 0.16, border: 0.6, targetLine: 0.9 },
  longHorizon: { fill: 0.08, border: 0.35, targetLine: 0.55 },
};
const LONG_HORIZON_INTERVALS = new Set(["1d", "1w", "1M"]);

const UP_COLOR = "38, 166, 154";
const DOWN_COLOR = "239, 83, 80";
const ACCENT_COLOR = "15, 157, 120";

// Nguong mau cho marker % chinh xac tren nen that (xem setAccuracyMarkers).
function accuracyColor(pct) {
  if (pct >= 90) return "#0f9d78";
  if (pct >= 70) return "#dd9a2e";
  return "#ef5350";
}

/**
 * Cac timestamp den tu backend deu la ISO string (REST: cot TIMESTAMPTZ bi
 * JSON.stringify tu dong goi thanh ISO string; WS: ingestion-service/
 * prediction-engine publish openTime/target_time dang ISO string, xem
 * klineNormalizer.js). Lightweight Charts can epoch giay (number) — parse
 * qua Date thay vi chia truc tiep cho 1000 (chia string se ra NaN).
 */
function toUnixSeconds(value) {
  if (typeof value === "number") return Math.floor(value / 1000);
  return Math.floor(new Date(value).getTime() / 1000);
}

/**
 * Tạo chart + realSeries + canvas overlay vẽ vùng giá dự đoán, gắn vào
 * container cho trước.
 * @param {HTMLElement} container
 * @returns {{ chart, realSeries, setRealData, updateRealCandle, updateForecastZone, clearForecastZone, setForecastStyleForInterval, setAccuracyMarkers, addAccuracyMarker, clearAccuracyMarkers, resize, destroy }}
 */
export function createChartRenderer(container) {
  const chart = createChart(container, {
    width: container.clientWidth,
    height: container.clientHeight,
    layout: {
      background: { color: "transparent" },
      textColor: "#8b93a7",
    },
    grid: {
      vertLines: { color: "rgba(139, 147, 167, 0.08)" },
      horzLines: { color: "rgba(139, 147, 167, 0.08)" },
    },
    crosshair: {
      mode: CrosshairMode.Normal,
    },
    rightPriceScale: {
      borderColor: "rgba(139, 147, 167, 0.2)",
    },
    timeScale: {
      borderColor: "rgba(139, 147, 167, 0.2)",
      timeVisible: true,
      secondsVisible: false,
      // Chừa sẵn khoảng trống bên phải để vùng giá dự đoán (kéo dài
      // PREDICTION_HORIZON bước vào tương lai, xem updateForecastZone) hiện
      // ra ngay mặc định, không cần user tự kéo/zoom chart mới thấy.
      rightOffset: 12,
    },
  });

  // Nến thực.
  const realSeries = chart.addCandlestickSeries({
    upColor: "#26a69a",
    downColor: "#ef5350",
    wickUpColor: "#26a69a",
    wickDownColor: "#ef5350",
    borderVisible: false,
  });

  // Canvas overlay vẽ vùng giá dự đoán — container cần position:relative
  // (xem main.css #chart-container) để canvas absolute neo đúng vị trí.
  const zoneCanvas = document.createElement("canvas");
  zoneCanvas.className = "forecast-zone-canvas";
  container.appendChild(zoneCanvas);
  const zoneCtx = zoneCanvas.getContext("2d");

  let zoneStyle = ZONE_STYLES.normal;
  // { fromTime, toTime, currentPrice, highPrice, lowPrice, targetPrice } | null
  let forecastZone = null;
  let destroyed = false;

  function resizeZoneCanvas() {
    const rect = container.getBoundingClientRect();
    const dpr = window.devicePixelRatio || 1;
    const targetW = Math.round(rect.width * dpr);
    const targetH = Math.round(rect.height * dpr);
    if (zoneCanvas.width !== targetW || zoneCanvas.height !== targetH) {
      zoneCanvas.width = targetW;
      zoneCanvas.height = targetH;
      zoneCanvas.style.width = `${rect.width}px`;
      zoneCanvas.style.height = `${rect.height}px`;
    }
    return dpr;
  }

  function drawZoneLabel(x, y, text, rgbColor, align) {
    zoneCtx.font = "bold 11px Inter, sans-serif";
    const paddingX = 6;
    const boxH = 18;
    const textWidth = zoneCtx.measureText(text).width;
    const boxW = textWidth + paddingX * 2;
    const boxX = x - boxW;
    const boxY = align === "top" ? y : y - boxH;

    zoneCtx.fillStyle = `rgb(${rgbColor})`;
    zoneCtx.fillRect(boxX, boxY, boxW, boxH);
    zoneCtx.fillStyle = "#ffffff";
    zoneCtx.textBaseline = "middle";
    zoneCtx.fillText(text, boxX + paddingX, boxY + boxH / 2 + 0.5);
  }

  /**
   * timeToCoordinate() CHỈ hoạt động cho thời điểm đã có dữ liệu thật trong
   * 1 series nào đó — trả về null cho mốc thời gian tương lai (vùng dự đoán
   * luôn ở tương lai, chưa có nến thật). Với thời điểm tương lai, ngoại suy
   * qua logical index (vị trí thứ tự thanh nến, có thể vượt quá thanh cuối
   * cùng) — logicalToCoordinate() hỗ trợ ngoại suy này dựa trên khoảng cách
   * giữa các thanh nến hiện tại, đây là cách chính thức lightweight-charts
   * hỗ trợ vẽ overlay vào vùng chưa có dữ liệu.
   */
  function timeToXWithExtrapolation(targetTime) {
    const data = realSeries.data();
    if (data.length === 0) return null;
    const lastTime = data[data.length - 1].time;

    if (targetTime <= lastTime) {
      return chart.timeScale().timeToCoordinate(targetTime);
    }
    if (data.length < 2) return null;

    const barIntervalSeconds = lastTime - data[data.length - 2].time;
    if (!barIntervalSeconds) return null;

    const lastX = chart.timeScale().timeToCoordinate(lastTime);
    if (lastX === null) return null;
    const lastLogical = chart.timeScale().coordinateToLogical(lastX);
    if (lastLogical === null) return null;

    const steps = Math.round((targetTime - lastTime) / barIntervalSeconds);
    return chart.timeScale().logicalToCoordinate(lastLogical + steps);
  }

  function drawForecastZone() {
    const dpr = resizeZoneCanvas();
    zoneCtx.setTransform(dpr, 0, 0, dpr, 0, 0);
    zoneCtx.clearRect(0, 0, zoneCanvas.clientWidth, zoneCanvas.clientHeight);

    if (!forecastZone) return;

    const x1 = timeToXWithExtrapolation(forecastZone.fromTime);
    let x2 = null;
    if (x1 !== null && typeof forecastZone.steps === "number") {
      const lastLogical = chart.timeScale().coordinateToLogical(x1);
      if (lastLogical !== null) {
        x2 = chart.timeScale().logicalToCoordinate(lastLogical + forecastZone.steps);
      }
    }
    if (x2 === null) {
      x2 = timeToXWithExtrapolation(forecastZone.toTime);
    }
    const yCurrent = realSeries.priceToCoordinate(forecastZone.currentPrice);
    const yHigh = realSeries.priceToCoordinate(forecastZone.highPrice);
    const yLow = realSeries.priceToCoordinate(forecastZone.lowPrice);
    const yTarget = realSeries.priceToCoordinate(forecastZone.targetPrice);

    if (x1 === null || x2 === null || yCurrent === null || yHigh === null || yLow === null) return;

    const left = Math.max(Math.min(x1, x2), 0);
    const right = Math.min(Math.max(x1, x2), zoneCanvas.clientWidth);
    if (right <= left) return;

    if (forecastZone.isSimulation) {
      const highPct = ((forecastZone.highPrice - forecastZone.currentPrice) / forecastZone.currentPrice) * 100;
      const lowPct = ((forecastZone.lowPrice - forecastZone.currentPrice) / forecastZone.currentPrice) * 100;
      const ratio = (Math.abs(lowPct) > 0 ? (highPct / Math.abs(lowPct)).toFixed(2) : "0.00");

      // Vùng xanh: Target zone
      zoneCtx.fillStyle = `rgba(${UP_COLOR}, 0.22)`;
      zoneCtx.fillRect(left, yHigh, right - left, yCurrent - yHigh);

      // Vùng đỏ: Stop zone
      zoneCtx.fillStyle = `rgba(${DOWN_COLOR}, 0.22)`;
      zoneCtx.fillRect(left, yCurrent, right - left, yLow - yCurrent);

      // Viền bao quanh.
      zoneCtx.strokeStyle = `rgba(139, 147, 167, 0.6)`;
      zoneCtx.lineWidth = 1;
      zoneCtx.strokeRect(left, yHigh, right - left, yLow - yHigh);

      // Đường entry ở giữa
      zoneCtx.strokeStyle = "rgba(139, 147, 167, 0.8)";
      zoneCtx.lineWidth = 1;
      zoneCtx.beginPath();
      zoneCtx.moveTo(left, yCurrent);
      zoneCtx.lineTo(right, yCurrent);
      zoneCtx.stroke();

      // Vẽ nhãn
      drawZoneLabel(right - 2, yHigh + 2, `Target: +${highPct.toFixed(2)}%`, UP_COLOR, "top");
      drawZoneLabel(right - 2, yLow - 2, `Stop: ${lowPct.toFixed(2)}%`, DOWN_COLOR, "bottom");
      
      const labelText = `R/R: ${ratio}`;
      const textW = zoneCtx.measureText(labelText).width;
      drawZoneLabel(left + 2 + textW + 12, yCurrent - 9, labelText, "139, 147, 167", "top");
    } else {
      // Vùng xanh: từ giá hiện tại lên tới đỉnh dự đoán (tiềm năng tăng).
      zoneCtx.fillStyle = `rgba(${UP_COLOR}, ${zoneStyle.fill})`;
      zoneCtx.fillRect(left, yHigh, right - left, yCurrent - yHigh);

      // Vùng đỏ: từ giá hiện tại xuống đáy dự đoán (tiềm năng giảm).
      zoneCtx.fillStyle = `rgba(${DOWN_COLOR}, ${zoneStyle.fill})`;
      zoneCtx.fillRect(left, yCurrent, right - left, yLow - yCurrent);

      // Viền bao quanh toàn bộ vùng.
      zoneCtx.strokeStyle = `rgba(139, 147, 167, ${zoneStyle.border})`;
      zoneCtx.lineWidth = 1;
      zoneCtx.strokeRect(left, yHigh, right - left, yLow - yHigh);

      // Đường mục tiêu (giá dự đoán ở bước xa nhất) — nét đứt màu accent.
      if (yTarget !== null) {
        zoneCtx.strokeStyle = `rgba(${ACCENT_COLOR}, ${zoneStyle.targetLine})`;
        zoneCtx.lineWidth = 1.5;
        zoneCtx.setLineDash([5, 4]);
        zoneCtx.beginPath();
        zoneCtx.moveTo(left, yTarget);
        zoneCtx.lineTo(right, yTarget);
        zoneCtx.stroke();
        zoneCtx.setLineDash([]);
      }

      const highPct = ((forecastZone.highPrice - forecastZone.currentPrice) / forecastZone.currentPrice) * 100;
      const lowPct = ((forecastZone.lowPrice - forecastZone.currentPrice) / forecastZone.currentPrice) * 100;
      const targetPct = ((forecastZone.targetPrice - forecastZone.currentPrice) / forecastZone.currentPrice) * 100;

      drawZoneLabel(right - 2, yHigh + 2, `+${highPct.toFixed(2)}%`, UP_COLOR, "top");
      drawZoneLabel(right - 2, yLow - 2, `${lowPct.toFixed(2)}%`, DOWN_COLOR, "bottom");
      if (yTarget !== null) {
        const sign = targetPct >= 0 ? "+" : "";
        drawZoneLabel(left + 2 + zoneCtx.measureText(`${sign}${targetPct.toFixed(2)}%`).width + 12, yTarget - 9, `${sign}${targetPct.toFixed(2)}%`, ACCENT_COLOR, "top");
      }
    }
  }

  /**
   * Đổi độ đậm của vùng dự đoán theo khung thời gian — 1d/1w/1M mờ hơn hẳn
   * 1m/1h vì dự đoán càng xa càng kém chắc chắn (xem ZONE_STYLES).
   */
  function setForecastStyleForInterval(interval) {
    zoneStyle = LONG_HORIZON_INTERVALS.has(interval) ? ZONE_STYLES.longHorizon : ZONE_STYLES.normal;
  }

  /**
   * Nạp vùng giá dự đoán từ dải multi-step forecast (xem
   * prediction-engine::predict_next_n_candles): đỉnh/đáy vùng lấy min/max
   * high/low trên TOÀN BỘ dải N bước, đường mục tiêu là predicted_close của
   * bước XA NHẤT (t+N) — "kỳ vọng" sau toàn bộ khoảng dự đoán.
   * @param {Array<{target_time:string|number, predicted_open:number, predicted_high:number, predicted_low:number, predicted_close:number}>} predictions
   * @param {boolean} isSimulation
   */
  function updateForecastZone(predictions, isSimulation = false) {
    if (!Array.isArray(predictions) || predictions.length === 0) {
      forecastZone = null;
      return;
    }

    const realData = realSeries.data();
    if (realData.length === 0) {
      forecastZone = null;
      return;
    }
    const currentPrice = Number(realData[realData.length - 1].close);
    const fromTime = realData[realData.length - 1].time;

    const sorted = [...predictions].sort(
      (a, b) => toUnixSeconds(a.target_time) - toUnixSeconds(b.target_time)
    );
    const highPrice = Math.max(...sorted.map((p) => Number(p.predicted_high)));
    const lowPrice = Math.min(...sorted.map((p) => Number(p.predicted_low)));
    const last = sorted[sorted.length - 1];

    forecastZone = {
      fromTime,
      toTime: toUnixSeconds(last.target_time),
      currentPrice,
      highPrice: Math.max(highPrice, currentPrice),
      lowPrice: Math.min(lowPrice, currentPrice),
      targetPrice: Number(last.predicted_close),
      steps: sorted.length,
      isSimulation,
    };
  }

  /**
   * Xoá vùng dự đoán — dùng khi đổi symbol/interval (dự đoán cũ không còn
   * liên quan tới cặp mới).
   */
  function clearForecastZone() {
    forecastZone = null;
  }

  /**
   * Nạp toàn bộ lịch sử nến thực vào chart.
   * @param {Array<{open_time:number, open:number, high:number, low:number, close:number}>} klines
   */
  function setRealData(klines) {
    const data = klines
      .map((k) => ({
        time: toUnixSeconds(k.open_time),
        open: Number(k.open),
        high: Number(k.high),
        low: Number(k.low),
        close: Number(k.close),
      }))
      .sort((a, b) => a.time - b.time);
    realSeries.setData(data);
  }

  /**
   * Cập nhật/thêm 1 nến thực (dùng cho realtime kline update — payload đến
   * từ WS "kline" event, field tên "openTime" chứ không phải "open_time"
   * như response REST /api/v1/klines, xem klineNormalizer.js).
   */
  function updateRealCandle(kline) {
    realSeries.update({
      time: toUnixSeconds(kline.openTime),
      open: Number(kline.open),
      high: Number(kline.high),
      low: Number(kline.low),
      close: Number(kline.close),
    });
  }

  let accuracyMarkers = [];

  /**
   * Nạp toàn bộ marker % chính xác lên nến thật (dùng khi load lịch sử —
   * xem GET /api/v1/accuracy?...&interval=). Chỉ dùng cho 1d/1w/1M vì
   * 1m/1h nến đóng quá dày, gắn marker từng nến sẽ rối chart — main.js
   * quyết định KHI NÀO gọi hàm này, chartRenderer chỉ lo phần vẽ.
   * @param {Array<{open_time:string|number, accuracy_pct:number}>} records
   */
  function setAccuracyMarkers(records) {
    accuracyMarkers = records
      .map((r) => ({
        time: toUnixSeconds(r.open_time),
        position: "aboveBar",
        color: accuracyColor(Number(r.accuracy_pct)),
        shape: "circle",
        text: `${Number(r.accuracy_pct).toFixed(1)}%`,
      }))
      .sort((a, b) => a.time - b.time);
    realSeries.setMarkers(accuracyMarkers);
  }

  /**
   * Thêm/cập nhật 1 marker (dùng khi có accuracy_update mới qua WS thời gian
   * thực) — thay marker cũ nếu trùng thời điểm nến, không thì thêm mới.
   */
  function addAccuracyMarker(record) {
    const marker = {
      time: toUnixSeconds(record.open_time),
      position: "aboveBar",
      color: accuracyColor(Number(record.accuracy_pct)),
      shape: "circle",
      text: `${Number(record.accuracy_pct).toFixed(1)}%`,
    };
    accuracyMarkers = accuracyMarkers.filter((m) => m.time !== marker.time);
    accuracyMarkers.push(marker);
    accuracyMarkers.sort((a, b) => a.time - b.time);
    realSeries.setMarkers(accuracyMarkers);
  }

  function clearAccuracyMarkers() {
    accuracyMarkers = [];
    realSeries.setMarkers([]);
  }

  function resize() {
    chart.applyOptions({
      width: container.clientWidth,
      height: container.clientHeight,
    });
  }

  const resizeObserver = new ResizeObserver(() => resize());
  resizeObserver.observe(container);

  // Vùng dự đoán vẽ trên canvas riêng, cần tự đồng bộ lại theo pan/zoom/scale
  // giá — lightweight-charts v4 không bắn event cho MỌI thay đổi (vd
  // autoscale khi có nến mới), nên dùng rAF loop la cach chac chan nhat.
  function loop() {
    if (destroyed) return;
    drawForecastZone();
    requestAnimationFrame(loop);
  }
  loop();

  function destroy() {
    destroyed = true;
    resizeObserver.disconnect();
    zoneCanvas.remove();
    chart.remove();
  }

  return {
    chart,
    realSeries,
    setRealData,
    updateRealCandle,
    updateForecastZone,
    clearForecastZone,
    setForecastStyleForInterval,
    setAccuracyMarkers,
    addAccuracyMarker,
    clearAccuracyMarkers,
    resize,
    destroy,
  };
}
