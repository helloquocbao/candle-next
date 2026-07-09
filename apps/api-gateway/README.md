# api-gateway

REST + WebSocket gateway — cửa ngõ duy nhất cho frontend.

- `src/routes/` — REST endpoints (`/klines`, `/predictions`, `/accuracy`, `/symbols`)
- `src/ws/` — WebSocket handlers (subscribe/kline/prediction/accuracy_update)
- `src/middleware/` — rate limit, CORS, validation
- `src/config/` — biến môi trường, kết nối DB/Redis
- Không gọi trực tiếp Binance — luôn đọc qua `ingestion-service`/DB/Redis

## Chạy local

1. Cài dependencies:

   ```bash
   npm install
   ```

2. Tạo file `.env` (hoặc export biến môi trường) với các biến sau:

   | Biến | Mô tả | Ví dụ |
   |---|---|---|
   | `DATABASE_URL` | Connection string PostgreSQL/TimescaleDB | `postgres://postgres:postgres@localhost:5432/crypto_predictor` |
   | `REDIS_URL` | Connection string Redis (pub/sub) | `redis://localhost:6379` |
   | `API_PORT` | Port lắng nghe của service (mặc định `8080`) | `8080` |
   | `CORS_ORIGIN` | Danh sách origin FE được phép, phân cách dấu phẩy (`*` = cho phép tất cả) | `http://localhost:3000,https://app.example.com` |

3. Chạy service:

   ```bash
   npm start
   ```

   Service sẽ expose REST API tại `/api/v1/*`, health check tại `/health`, và WebSocket server gắn trên cùng port (path mặc định).
