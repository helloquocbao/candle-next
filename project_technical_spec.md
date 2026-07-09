# Tài liệu Kỹ thuật — Crypto Real-time Predictor Chart

Phiên bản: 1.0 · Ngày: 07/07/2026 · Dựa trên: `project_overview.md`

---

## 1. Mục tiêu & Phạm vi

Xây dựng hệ thống vẽ biểu đồ nến crypto real-time, tích hợp thuật toán tự học để dự đoán các cây nến tương lai, hiển thị trực tiếp trên chart, và tự tối ưu tham số dựa trên sai số thực tế. Tài liệu này mô tả kiến trúc, thiết kế dữ liệu, thuật toán, hạ tầng triển khai và các yêu cầu phi chức năng (bảo mật, hiệu năng, giám sát) để đội kỹ thuật có thể triển khai trực tiếp.

Ngoài phạm vi: sàn giao dịch nội bộ (không tự custody tài sản người dùng), ví điện tử, KYC/AML.

---

## 2. Kiến trúc tổng thể

```
                        ┌─────────────────────┐
                        │   Binance API        │
                        │  REST (klines lịch sử)│
                        │  WebSocket (real-time)│
                        └──────────┬───────────┘
                                   │
                     ┌─────────────▼──────────────┐
                     │      Data Ingestion Service  │
                     │  (Node.js/Python worker)     │
                     └─────────────┬──────────────┘
                                   │
                ┌──────────────────┼───────────────────┐
                │                  │                   │
     ┌──────────▼─────────┐ ┌──────▼───────┐ ┌─────────▼─────────┐
     │  TimescaleDB/       │ │  Redis        │ │ Prediction Engine  │
     │  PostgreSQL          │ │  (cache/pubsub)│ │ (ML/Genetic Algo)  │
     │  (klines, logs)      │ │               │ │                    │
     └──────────┬─────────┘ └──────┬───────┘ └─────────┬─────────┘
                │                  │                   │
                └──────────┬───────┴─────────┬─────────┘
                           │                 │
                  ┌────────▼────────┐ ┌──────▼───────┐
                  │  API Gateway      │ │ WebSocket     │
                  │  (REST, Nginx)    │ │ Gateway (WSS) │
                  └────────┬────────┘ └──────┬───────┘
                           │                 │
                           └────────┬────────┘
                                    │
                          ┌─────────▼─────────┐
                          │   Frontend (SPA)    │
                          │ TradingView          │
                          │ Lightweight Charts   │
                          └─────────────────────┘
```

**Thành phần chính:**

| Thành phần | Công nghệ đề xuất | Vai trò |
|---|---|---|
| Data Ingestion Service | Node.js (ws) hoặc Python (websockets/ccxt) | Kết nối Binance REST + WebSocket, chuẩn hoá dữ liệu nến |
| Prediction Engine | Python (scikit-learn/PyTorch hoặc thuật toán di truyền tự viết) | Huấn luyện, dự đoán, tối ưu tham số online |
| Message Broker | Redis Pub/Sub hoặc Kafka (giai đoạn scale) | Truyền dữ liệu giữa các service |
| Database | TimescaleDB (PostgreSQL extension cho time-series) | Lưu klines, dự đoán, log độ chính xác |
| API Gateway | Nginx + Express/FastAPI | REST endpoints, reverse proxy, TLS termination |
| WebSocket Gateway | Socket.IO hoặc native `ws` | Đẩy dữ liệu real-time tới client |
| Frontend | HTML/JS + TradingView Lightweight Charts | Vẽ nến thực + nến dự đoán (RGBA mờ) |
| Orchestration | Docker Compose (giai đoạn đầu) → có thể nâng cấp K8s | Đóng gói & triển khai |

---

## 3. Data Layer

### 3.1 Nguồn dữ liệu Binance

- **REST**: `GET /api/v3/klines` — lấy dữ liệu lịch sử để bootstrap và huấn luyện mô hình ban đầu.
- **WebSocket**: `wss://stream.binance.com:9443/ws/<symbol>@kline_<interval>` — nhận nến real-time (cập nhật mỗi giây cho nến đang hình thành, đóng nến theo interval).
- **Giới hạn cần lưu ý**: rate limit REST (1200 request weight/phút), giới hạn số kết nối WebSocket đồng thời (tối đa 5 luồng/kết nối, 300 kết nối/5 phút mỗi IP) → cần connection pooling và exponential backoff khi reconnect.

### 3.2 Schema dữ liệu (TimescaleDB)

```sql
-- Bảng nến thực tế
CREATE TABLE klines (
    symbol       TEXT NOT NULL,
    interval     TEXT NOT NULL,
    open_time    TIMESTAMPTZ NOT NULL,
    open         NUMERIC NOT NULL,
    high         NUMERIC NOT NULL,
    low          NUMERIC NOT NULL,
    close        NUMERIC NOT NULL,
    volume       NUMERIC NOT NULL,
    close_time   TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (symbol, interval, open_time)
);
SELECT create_hypertable('klines', 'open_time');

-- Bảng nến dự đoán
CREATE TABLE predictions (
    id            BIGSERIAL,
    symbol        TEXT NOT NULL,
    interval      TEXT NOT NULL,
    target_time   TIMESTAMPTZ NOT NULL,   -- thời điểm nến dự đoán sẽ đóng
    predicted_open  NUMERIC,
    predicted_high  NUMERIC,
    predicted_low   NUMERIC,
    predicted_close NUMERIC,
    confidence      NUMERIC,              -- 0..1
    model_version   TEXT,
    created_at      TIMESTAMPTZ DEFAULT now(),
    PRIMARY KEY (id, created_at)
);
SELECT create_hypertable('predictions', 'created_at');

-- Bảng log độ chính xác (feedback loop)
CREATE TABLE accuracy_log (
    id              BIGSERIAL PRIMARY KEY,
    prediction_id   BIGINT,
    symbol          TEXT,
    interval        TEXT,
    actual_close    NUMERIC,
    predicted_close NUMERIC,
    error_pct       NUMERIC,
    accuracy_pct    NUMERIC,
    evaluated_at    TIMESTAMPTZ DEFAULT now()
);

-- Bảng tham số thuật toán theo thời gian (audit trail tối ưu hoá)
CREATE TABLE model_params_history (
    id           BIGSERIAL PRIMARY KEY,
    symbol       TEXT,
    params       JSONB,
    avg_accuracy NUMERIC,
    updated_at   TIMESTAMPTZ DEFAULT now()
);
```

---

## 4. Prediction Engine & Vòng lặp tự học

### 4.1 Lựa chọn thuật toán

- **Baseline**: mô hình thống kê (EMA/ARIMA) để có kết quả nhanh, làm nền tảng so sánh.
- **Machine Learning**: LSTM/GRU hoặc Gradient Boosting (LightGBM) trên feature kỹ thuật (RSI, MACD, Bollinger Bands, volume profile).
- **Genetic Algorithm**: tối ưu hoá siêu tham số (learning rate, window size, trọng số feature) theo chu kỳ, phù hợp bài toán tối ưu online không cần gradient.

### 4.2 Pseudocode vòng lặp self-learning

```python
while True:
    candle_t = get_current_forming_candle(symbol, interval)
    prediction = model.predict(candle_t, history_window)
    render_ghost_candle(prediction)  # gửi qua WebSocket tới FE, vẽ RGBA mờ

    wait_until_candle_closes(interval)

    actual = get_closed_candle(symbol, interval)
    error = compute_error(actual, prediction)          # MAPE / RMSE
    accuracy = 100 - error
    log_accuracy(prediction.id, actual, accuracy)

    if should_optimize(accuracy_window):               # vd: mỗi N nến hoặc khi accuracy < ngưỡng
        new_params = genetic_algorithm.evolve(
            population=current_param_sets,
            fitness_fn=lambda p: backtest_accuracy(p, recent_history)
        )
        model.update_params(new_params)
        save_params_history(new_params)
```

### 4.3 Chỉ số đánh giá

- **MAPE** (Mean Absolute Percentage Error) cho giá close.
- **Direction Accuracy** (dự đoán đúng chiều tăng/giảm) — chỉ số quan trọng hơn giá trị tuyệt đối với trader.
- **Sharpe-like confidence score** để hiển thị độ tin cậy dự đoán trên UI.

### 4.4 Chống overfitting & rủi ro mô hình

- Walk-forward validation thay vì train/test tĩnh.
- Giới hạn biên độ điều chỉnh tham số mỗi vòng lặp (tránh dao động mạnh — "thrashing").
- Circuit breaker: nếu accuracy giảm liên tục qua N vòng, rollback về `model_params_history` gần nhất có accuracy cao.

---

## 5. Thiết kế API

### 5.1 REST Endpoints

| Method | Endpoint | Mô tả |
|---|---|---|
| GET | `/api/v1/klines?symbol=BTCUSDT&interval=1m&limit=500` | Lấy lịch sử nến |
| GET | `/api/v1/predictions/latest?symbol=BTCUSDT&interval=1m` | Lấy dự đoán nến tiếp theo |
| GET | `/api/v1/accuracy?symbol=BTCUSDT&range=24h` | Thống kê độ chính xác |
| GET | `/api/v1/symbols` | Danh sách cặp coin hỗ trợ |
| GET | `/health` | Health check cho load balancer |

### 5.2 WebSocket Events (client ⇄ server)

```
subscribe   -> { "action": "subscribe", "symbol": "BTCUSDT", "interval": "1m" }
kline       <- { "type": "kline", "data": {...} }              // nến thực real-time
prediction  <- { "type": "prediction", "data": {...} }         // nến dự đoán (ghost candle)
accuracy    <- { "type": "accuracy_update", "data": {...} }    // % chính xác mới nhất
```

---

## 6. Frontend

- **Thư viện**: TradingView Lightweight Charts (nhẹ, hiệu năng cao, hỗ trợ custom series).
- **Render nến dự đoán**: dùng `CandlestickSeries` phụ với `color`/`wickColor` ở dạng RGBA alpha thấp (vd: `rgba(255,255,255,0.35)`), cập nhật lại khi có prediction mới, xoá khi nến thực đóng lại (thay bằng nến thật).
- **State management**: nhẹ (vanilla JS hoặc React) — không cần Redux nếu chỉ có 1-2 chart view.
- **Kết nối dữ liệu**: WebSocket client tự động reconnect + heartbeat ping/pong.
- **Hiển thị % chính xác**: badge/label góc chart, cập nhật theo `accuracy_update`.

---

## 7. Hạ tầng & Triển khai (Deployment)

### 7.1 Kiến trúc Docker Compose

```yaml
services:
  ingestion:      # kết nối Binance, ghi vào DB + publish Redis
  prediction:     # chạy model, publish kết quả dự đoán
  api:            # REST + WebSocket gateway
  timescaledb:    # database
  redis:          # pub/sub + cache
  nginx:          # reverse proxy + SSL termination (wss://)
```

### 7.2 Môi trường

- **Frontend**: Vercel hoặc GitHub Pages (miễn phí, CDN toàn cầu).
- **Backend**: VPS Ubuntu 22.04 (Hetzner/DigitalOcean), tối thiểu 2 vCPU / 4GB RAM cho giai đoạn MVP.
- **SSL/TLS**: Let's Encrypt (Certbot) cho domain `.xyz/.tech`, bắt buộc cho `wss://`.
- **CI/CD**: GitHub Actions — build & push Docker image, SSH deploy hoặc webhook tới VPS.
- **Backup**: snapshot VPS hàng tuần + pg_dump định kỳ cho TimescaleDB.

### 7.3 Ước tính chi phí (khớp với overview)

| Hạng mục | Chi phí/tháng |
|---|---|
| VPS (2vCPU/4GB) | ~$5 |
| Domain (.xyz/.tech) | ~$1-2 (quy đổi theo năm) |
| SSL | Miễn phí (Let's Encrypt) |
| Frontend hosting | Miễn phí (Vercel/GitHub Pages) |
| **Tổng** | **~$5-7/tháng** |

---

## 8. Bảo mật

- Giới hạn rate limit tại Nginx/API Gateway để chống abuse (đặc biệt endpoint public không auth).
- Không lưu trữ private key hay thông tin tài khoản Binance của người dùng (chỉ dùng public market data API).
- CORS whitelist domain frontend chính thức.
- WSS bắt buộc (không cho phép `ws://` plaintext ở production).
- Input validation cho mọi query param (symbol/interval) để tránh injection vào truy vấn DB.
- Secrets (API keys mạng quảng cáo, affiliate ID) lưu trong biến môi trường/secret manager, không hardcode.

---

## 9. Giám sát & Vận hành (Observability)

- **Logging**: structured logs (JSON) cho ingestion/prediction service, tập trung qua Loki hoặc file rotate đơn giản ở giai đoạn MVP.
- **Metrics**: Prometheus + Grafana (giai đoạn 2) theo dõi độ trễ WebSocket, tỷ lệ mất kết nối Binance, accuracy trung bình theo thời gian.
- **Alerting**: cảnh báo khi accuracy giảm dưới ngưỡng, khi ingestion service mất kết nối > 30s.

---

## 10. Rủi ro kỹ thuật & Giải pháp

| Rủi ro | Giải pháp |
|---|---|
| Binance rate limit / mất kết nối WebSocket | Reconnect với backoff, fallback sang REST polling tạm thời |
| Mô hình dự đoán kém chính xác gây mất niềm tin người dùng | Hiển thị rõ confidence score, disclaimer "không phải lời khuyên tài chính" |
| Chi phí VPS tăng khi traffic lớn | Thiết kế stateless cho API service để dễ scale ngang, cache Redis giảm tải DB |
| Quảng cáo crypto bị chặn bởi trình duyệt/AdBlock | Đa dạng hoá nguồn doanh thu (xem `monetization_strategies.md`) |

---

## 11. Roadmap đề xuất

1. **Giai đoạn 1 (MVP, 2-4 tuần)**: ingestion + chart real-time cơ bản, chưa có dự đoán.
2. **Giai đoạn 2 (4-6 tuần)**: tích hợp prediction engine baseline (EMA/thống kê) + vẽ ghost candle.
3. **Giai đoạn 3 (6-8 tuần)**: nâng cấp ML/Genetic Algorithm, vòng lặp self-learning đầy đủ, dashboard accuracy.
4. **Giai đoạn 4**: tích hợp monetization (ads, affiliate), tối ưu hạ tầng, mở rộng thêm cặp coin.

---

## 12. Tài liệu liên quan

- `project_overview.md` — tóm tắt ý tưởng & chiến lược doanh thu ban đầu.
- `monetization_strategies.md` — các phương pháp tạo doanh thu bổ sung không thu phí người dùng.
