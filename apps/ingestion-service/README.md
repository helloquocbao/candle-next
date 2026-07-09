# ingestion-service

Kết nối Binance REST + WebSocket, chuẩn hoá dữ liệu, ghi vào DB và publish Redis.

- `src/connectors/` — Binance REST client, WebSocket client (reconnect/backoff)
- `src/normalizers/` — chuẩn hoá payload thành schema `klines` chung
- Chạy độc lập, không phục vụ HTTP request từ client ngoài

## Chạy local

1. Cài dependencies:

   ```bash
   npm install
   ```

2. Thiết lập biến môi trường (có thể export trực tiếp hoặc tạo file `.env` trong thư mục này — service dùng `dotenv` để tự load):

   ```bash
   export DATABASE_URL="postgres://user:password@localhost:5432/crypto_predictor"
   export REDIS_URL="redis://localhost:6379"
   ```

   Danh sách symbol/interval cần theo dõi được phân giải theo thứ tự ưu tiên (xem `src/trackedPairs.js`):

   1. `SYMBOL_PAIRS="BTCUSDT:1m,ETHUSDT:1m,SOLUSDT:1m"` — override thủ công, tiện cho dev/test 1 process theo dõi nhiều cặp.
   2. Bảng `tracked_pairs` trong DB (`infra/db/migrations/002_tracked_pairs.sql`) — nguồn cấu hình chung của toàn hệ thống, không cần redeploy để thêm/bớt cặp.
   3. `SYMBOL`/`INTERVAL` riêng lẻ (tương thích ngược) — mặc định `BTCUSDT`/`1m` nếu không set gì cả.

   Lưu ý: bảng `klines` cần được tạo sẵn trong Postgres/TimescaleDB theo schema mô tả tại `project_technical_spec.md` (mục 3.2) trước khi chạy service.

3. Chạy service:

   ```bash
   npm start
   ```

   Service sẽ chạy song song 1 pipeline bootstrap+realtime cho từng cặp symbol/interval đã phân giải ở trên: bootstrap lịch sử qua REST (`GET /api/v3/klines`) và ghi vào DB, sau đó mở WebSocket real-time tới Binance, publish mọi update (kể cả nến đang hình thành) lên Redis channel `klines:<symbol>:<interval>`, và chỉ ghi vào DB khi nến đã đóng (`isClosed = true`).

### Chạy bằng Docker

```bash
docker build -t ingestion-service .
docker run --rm \
  -e DATABASE_URL="postgres://user:password@host:5432/crypto_predictor" \
  -e REDIS_URL="redis://host:6379" \
  -e SYMBOL="BTCUSDT" \
  -e INTERVAL="1m" \
  ingestion-service
```
