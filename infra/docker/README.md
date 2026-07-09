# infra/docker

`docker-compose.yml` gốc điều phối phần **backend**: `ingestion`, `prediction`, `api`, `timescaledb`, `redis`, `nginx`. Frontend KHÔNG nằm trong cụm này — deploy độc lập trên Vercel (xem `apps/frontend/README.md` mục "Deploy lên Vercel").

Dockerfile của từng service backend (`api-gateway`, `ingestion-service`, `prediction-engine`) nằm ngay trong thư mục `apps/<tên-app>/Dockerfile` tương ứng — `docker-compose.yml` chỉ trỏ `build.context`/`build.dockerfile` tới đó.

## Services

| Service | Build từ | Ghi chú |
|---|---|---|
| `ingestion` | `apps/ingestion-service` | Kết nối Binance, ghi DB + publish Redis. Chờ `timescaledb`/`redis` healthy mới start. |
| `prediction` | `apps/prediction-engine` | Chạy model, publish dự đoán. Chờ `timescaledb`/`redis` healthy. |
| `api` | `apps/api-gateway` | REST + WebSocket gateway, publish port `8080`. Chờ `timescaledb`/`redis` healthy. |
| `timescaledb` | image `timescale/timescaledb:latest-pg16` | Tự động chạy migration `infra/db/migrations/*.sql` khi khởi tạo lần đầu (mount vào `/docker-entrypoint-initdb.d`). Có healthcheck `pg_isready`. |
| `redis` | image `redis:7-alpine` | Pub/sub + cache. Có healthcheck `redis-cli ping`. |
| `nginx` | image `nginx:alpine` | Reverse proxy/SSL termination cho domain BACKEND (vd `api.yourdomain.com`), route `/api/` và `/ws` → `api`. Cấu hình tại `nginx/default.conf`. |

## Vì sao tách frontend ra khỏi cụm Docker này

Frontend là build tĩnh (HTML/CSS/JS thuần sau `npm run build`, xem giải thích trong `apps/frontend/README.md`) — không cần server Node/Docker để chạy logic, chỉ cần một static host trả file. Deploy lên Vercel (miễn phí, CDN toàn cầu, tự build khi push code) hợp lý hơn nhiều so với tự chạy container Nginx serve static trên VPS. `apps/frontend/Dockerfile` vẫn còn trong repo để có thể test full-stack bằng Docker ở local nếu muốn, nhưng production dùng Vercel.

Vì frontend (Vercel) và backend (VPS, qua `nginx` này) nằm ở 2 domain khác nhau, cần:
- `CORS_ORIGIN` trong `.env` của backend phải liệt kê đúng domain Vercel.
- Backend phải có SSL thật (`https://`/`wss://`) — trình duyệt chặn gọi `http://`/`ws://` từ trang HTTPS trên Vercel (mixed content).

## SSL/WSS (production)

Xem TODO trong `docker-compose.yml` (mount `/etc/letsencrypt`) và `nginx/default.conf` (bật `listen 443 ssl`, redirect 80→443, cấu hình Certbot) — cần hoàn thiện trước khi go-live theo mục 8, `project_technical_spec.md`. Đây là điều kiện bắt buộc để frontend Vercel (luôn HTTPS) gọi được vào backend.
