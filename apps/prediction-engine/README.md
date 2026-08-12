# prediction-engine

Thuật toán dự đoán nến + vòng lặp tự học.

- `src/models/` — baseline (EMA/ARIMA), ML (LSTM/LightGBM)
- `src/training/` — huấn luyện offline/batch
- `src/optimization/` — Genetic Algorithm tối ưu tham số online
- `src/evaluation/` — tính MAPE, direction accuracy, ghi `accuracy_log`

## Trạng thái hiện tại (baseline + self-learning loop)

Service implement **baseline** (EMA đơn giản trên giá close + ATR đơn giản
để ước lượng high/low) VÀ vòng lặp self-learning theo Giai đoạn 3 của roadmap
(`project_technical_spec.md` mục 11):

- `src/optimization/genetic.py` — Genetic Algorithm THẬT (selection bằng
  tournament, uniform crossover, mutation giới hạn biên độ, elitism, dừng
  khi hội tụ). Có thêm `optimize_params_with_validation()` implement cơ chế
  rollback/circuit breaker (spec mục 4.4): chỉ áp dụng tham số mới nếu nó
  cũng tốt hơn (hoặc bằng) trên một tập validation riêng — **thực nghiệm cho
  thấy đây là bắt buộc**: GA tối ưu trên 1 tập dữ liệu rất dễ overfit (tham
  số tốt trên train nhưng tệ hơn cả mặc định trên dữ liệu chưa thấy).
- `src/evaluation/backtest.py` — `score_params()`: walk-forward scoring dùng
  chung giữa backtest offline và vòng lặp online trong `main.py`.
- `src/main.py` — `PredictionEngine` giờ tự động: mỗi `OPTIMIZE_EVERY_N_EVALUATIONS`
  lần đánh giá (mặc định 30), tách buffer nến gần nhất thành train/validation
  nội bộ, chạy GA, chỉ cập nhật `ema_span`/`lookback` nếu generalize được, và
  ghi lại vào `model_params_history` (audit trail).

- `src/evaluation/calibration.py` — `calibrate_confidence()`: confidence gốc
  từ `models/baseline.py` chỉ dựa trên volatility, KHÔNG tương quan với khả
  năng dự đoán đúng chiều thực tế (đo được qua backtest). Hàm này tính lại
  confidence bằng cách trộn với tỉ lệ dự đoán đúng chiều **thực tế** gần đây
  (`accuracy_history`), được nối vào `main.py::_make_new_prediction`.

**Đã biết (từ thực nghiệm backtest trên dữ liệu BTCUSDT thật)**: baseline EMA
đơn lẻ chỉ đạt direction accuracy ~50-56% (gần tung xu ngẫu nhiên) và MAPE
thường KÉM HƠN heuristic "giá không đổi" — xem mục 4.1 spec về roadmap nâng
cấp lên ML (LSTM/LightGBM) với nhiều feature kỹ thuật hơn (RSI, MACD, volume)
để có edge thực sự thay vì chỉ tinh chỉnh 2 siêu tham số của 1 model tuyến tính.

**Về confidence/calibration**: quan trọng — không có cách nao lam confidence
*phan biet* (discriminate) tot hon giua cac nen rieng le khi model khong co
edge thuc su (~52% direction accuracy, gan coin-flip). Cai `calibrate_confidence()`
lam duoc la *calibration* (confidence trung binh phan anh dung ti le chinh
xac trung binh), khong phai *discrimination*. Do tren 200 du doan lien tiep
(BTCUSDT 1m thuc): confidence goc bao cao trung binh 95.9% trong khi accuracy
thuc te chi 52-54% (lech 42-44 diem %, hoan toan gay hieu ung — nguoi dung se
tin sai). Sau calibrate (`realized_weight=0.85`): confidence trung binh giam
ve ~59-63%, gan sat accuracy thuc te hon nhieu (lech con ~7-12 diem %), va
Brier score (thang do calibration chuan) giam tu ~0.42-0.44 xuong ~0.27 —
cai thien ro rang va co the do lai bat cu luc nao qua backtest.

### Generalization: đã xác nhận trên nhiều symbol (không chỉ BTCUSDT)

Backtest lại tren ETHUSDT, SOLUSDT, DOGEUSDT (1m va 1h, du lieu thuc tu Binance)
cho cung ket qua nhu BTCUSDT:

| Symbol | Interval | Baseline DirectionAcc | Baseline MAPE vs naive |
|---|---|---|---|
| ETHUSDT | 1m | 52.04% | 1.67x kem hon |
| ETHUSDT | 1h | 48.24% | 1.71x kem hon |
| SOLUSDT | 1m | 47.04% | 1.71x kem hon |
| SOLUSDT | 1h | 50.88% | 1.63x kem hon |
| DOGEUSDT | 1m | 46.48% | 1.71x kem hon |
| DOGEUSDT | 1h | 51.18% | 1.65x kem hon |

**Kết luận**: đây là giới hạn nhất quán của kiến trúc baseline (1 feature duy
nhất — giá close, qua EMA), không phải đặc thù của 1 coin nào. Genetic
Algorithm (dù đã implement đúng và có validation/rollback) không thể tạo ra
edge từ 1 feature không mang tín hiệu dự đoán — GA chỉ tối ưu được best-case
trong không gian tham số hiện có, và best-case đó vẫn chỉ là ~50% direction
accuracy. **Bước tiếp theo có ý nghĩa KHÔNG phải là tinh chỉnh thêm EMA/GA**,
mà là nâng cấp lên Giai đoạn 3 của roadmap (`project_technical_spec.md` mục
4.1): model ML thật (LSTM/GRU hoặc LightGBM) với nhiều feature kỹ thuật hơn
(RSI, MACD, Bollinger Bands, volume profile, multi-timeframe) — đây là quyết
định kiến trúc lớn (thêm dependency scikit-learn/PyTorch/LightGBM, cần dữ
liệu training, thay đổi pipeline) nên cần được xác nhận với chủ dự án trước
khi triển khai, không tự động thực hiện trong vòng lặp audit/backtest này.

## Ensemble AI (DeepSeek)

`src/ai_advisor.py` — tín hiệu BỔ SUNG (ensemble) từ DeepSeek Chat API kết
hợp với baseline/LightGBM+GA, KHÔNG thay thế. Chỉ áp dụng cho bước **t+1**
(bước duy nhất được theo dõi accuracy, xem ghi chú `PREDICTION_HORIZON`
trong `main.py`) — các bước t+2..t+N vẫn thuần định lượng như trước.

Cách hoạt động: mỗi `AI_REFRESH_EVERY_N_CANDLES` nến đóng (mặc định `3`, nên
tăng lên với interval ngắn như `1m` để giới hạn chi phí/API rate limit), gọi
DeepSeek với giá đóng cửa gần đây + dự đoán của model định lượng, nhận về
`{direction, predicted_change_pct, confidence, reasoning}`, rồi blend theo
trọng số `DEEPSEEK_WEIGHT` (mặc định `0.35` — model định lượng vẫn là tín
hiệu chính). Nếu 2 nguồn **bất đồng chiều**, confidence cuối cùng bị nhân
thêm `DEEPSEEK_DISAGREEMENT_PENALTY` (mặc định `0.5`) để phản ánh đúng mức
độ không chắc chắn của ensemble.

**Mặc định TẮT** (`DEEPSEEK_ENABLED=false`) — bật bằng cách set
`DEEPSEEK_ENABLED=true` và `DEEPSEEK_API_KEY` (xem `.env.example`). Thiếu
API key dù bật cờ sẽ tự động tắt lại + log warning, không crash. Mọi lỗi
mạng/timeout/JSON không parse được đều fallback về đúng tín hiệu định lượng
gốc — không bao giờ chặn luồng dự đoán real-time vì 1 dịch vụ AI bên ngoài.

**Audit trail**: mỗi tín hiệu AI được blend đều ghi vào bảng `ai_signals`
(`infra/db/migrations/006_ai_signals.sql`), và `model_version` của bước t+1
được gắn thêm hậu tố `+deepseek` (vd `baseline-ema-v1+deepseek`). Điều này
cho phép sau này lọc `accuracy_log` theo `model_version` để so sánh khách
quan: ensemble có thực sự cải thiện direction accuracy so với baseline/GA
đơn thuần hay không, TRƯỚC KHI tăng `DEEPSEEK_WEIGHT` hay coi đây là giải
pháp cho vấn đề ~50% direction accuracy đã nêu ở trên — bản thân việc thêm 1
LLM chat vào ensemble KHÔNG tự động đảm bảo có edge thực sự, cần đo lại y hệt
cách baseline/GA đã được đo (bảng backtest ở mục "Generalization" phía trên).

**Độ trễ**: gọi API đồng bộ trên thread xử lý của từng cặp (`_run_pair`),
timeout mặc định `DEEPSEEK_TIMEOUT_SEC=8`s — với interval `1m`, cân nhắc kỹ
`AI_REFRESH_EVERY_N_CANDLES` để tránh dồn ứ message Redis đang chờ xử lý.

## Chạy local

1. Cài dependency:

   ```bash
   cd apps/prediction-engine
   pip install -r requirements.txt
   ```

2. Chuẩn bị biến môi trường (có thể tạo file `.env` trong thư mục này, service
   dùng `python-dotenv` để tự load):

   ```env
   REDIS_URL=redis://localhost:6379
   DATABASE_URL=postgresql://user:password@localhost:5432/crypto_predictor
   ```

   - `REDIS_URL` — mặc định `redis://localhost:6379` nếu không set.
   - `DATABASE_URL` — bắt buộc để ghi `predictions` / `accuracy_log` (xem
     schema mục 3.2 `project_technical_spec.md`).

   Danh sách symbol/interval cần theo dõi được phân giải theo thứ tự ưu tiên
   (xem `src/tracked_pairs.py`, cùng logic với `ingestion-service`):

   1. `TRACKED_PAIRS=BTCUSDT:1m,ETHUSDT:1m,SOLUSDT:1m` — override thủ công.
   2. Bảng `tracked_pairs` trong DB (`infra/db/migrations/002_tracked_pairs.sql`).
   3. `SYMBOL`/`INTERVAL` riêng lẻ (tương thích ngược) — mặc định `BTCUSDT`/`1m`.

   Mỗi cặp chạy trên 1 thread riêng (1 `PredictionEngine` + 1 Redis pubsub
   độc lập/thread); các thao tác ghi DB được serialize qua 1 lock chung vì
   connection Postgres hiện dùng chung giữa các thread (xem `src/db.py`).

   Tùy chọn (vòng lặp self-learning — bỏ qua để dùng giá trị mặc định):

   - `OPTIMIZE_EVERY_N_EVALUATIONS` (mặc định `30`) — số lần đánh giá giữa
     mỗi lần chạy Genetic Algorithm.
   - `MIN_HISTORY_FOR_OPTIMIZE` (mặc định `80`) — số nến tối thiểu trong
     buffer để tách train/validation chạy GA có ý nghĩa.
   - `TRAIN_SPLIT_RATIO` (mặc định `0.7`) — tỉ lệ buffer dùng làm train (phần
     còn lại là validation cho rollback/circuit breaker). Phải trong (0, 1).
   - `ACCURACY_HISTORY_MAXLEN` (mặc định `200`) — số kết quả accuracy gần
     nhất giữ lại để tính `avg_accuracy` khi ghi `model_params_history`.
   - `CANDLE_BUFFER_MAXLEN` (mặc định `200`) — số nến gần nhất giữ trong
     buffer in-memory.

3. Đảm bảo Redis và PostgreSQL/TimescaleDB đã chạy, và bảng `predictions`,
   `accuracy_log` đã được tạo theo schema trong `project_technical_spec.md`.
   Service này subscribe channel `klines:<symbol>:<interval>` do
   `ingestion-service` publish — cần chạy `ingestion-service` song song (hoặc
   publish thủ công message đúng định dạng để test).

4. Chạy service:

   ```bash
   python src/main.py
   ```

Service sẽ subscribe Redis channel `klines:<SYMBOL>:<INTERVAL>`, và với mỗi
nến đã đóng (`isClosed: true`) sẽ: đánh giá accuracy của dự đoán trước đó
(nếu có), lưu nến vào buffer in-memory, tính dự đoán mới cho nến kế tiếp, ghi
DB và publish lên các channel `predictions:<symbol>:<interval>` và
`accuracy:<symbol>:<interval>`.

## Chạy bằng Docker

```bash
docker build -t prediction-engine .
docker run --env-file .env prediction-engine
```
