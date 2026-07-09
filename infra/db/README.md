# infra/db

`migrations/001_init.sql` — script SQL khởi tạo đầy đủ 4 bảng theo schema tại `project_technical_spec.md` mục 3.2:

- `klines` — nến thực tế (PK: `symbol, interval, open_time`), hypertable trên `open_time` nếu extension TimescaleDB có sẵn.
- `predictions` — nến dự đoán (PK: `id, created_at`), hypertable trên `created_at`.
- `accuracy_log` — log độ chính xác (feedback loop), PK `id BIGSERIAL`.
- `model_params_history` — audit trail tham số model theo thời gian (Genetic Algorithm), PK `id BIGSERIAL`.

Mỗi bảng truy vấn thường xuyên theo `(symbol, interval)` đều có index hỗ trợ (`idx_klines_symbol_interval_open_time`, `idx_predictions_symbol_interval_created_at`, `idx_predictions_symbol_interval_target_time`, `idx_accuracy_log_symbol_interval_evaluated_at`, `idx_accuracy_log_prediction_id`, `idx_model_params_history_symbol_updated_at`).

Script bọc `CREATE EXTENSION IF NOT EXISTS timescaledb;` và các lệnh `create_hypertable()` trong khối kiểm tra extension tồn tại, nên vẫn chạy an toàn kể cả trên PostgreSQL thuần (không có TimescaleDB) — khi đó các bảng hoạt động như bảng quan hệ thông thường.

## Chạy migration

- **Tự động**: `docker-compose.yml` mount `infra/db/migrations` vào `/docker-entrypoint-initdb.d` của container `timescaledb` — migration chạy tự động khi volume data rỗng (lần khởi tạo đầu tiên).
- **Thủ công**: `psql "$DATABASE_URL" -f infra/db/migrations/001_init.sql`.

Các migration tiếp theo (nếu có) nên đặt tên tăng dần (`002_*.sql`, `003_*.sql`, ...) để giữ thứ tự thực thi đúng.
