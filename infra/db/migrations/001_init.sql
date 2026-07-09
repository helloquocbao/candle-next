-- =============================================================================
-- Migration: 001_init.sql
-- Mục đích : Khởi tạo schema cho "Crypto Real-time Predictor Chart"
-- Nguồn    : project_technical_spec.md, mục 3.2 (Schema dữ liệu - TimescaleDB)
-- Áp dụng  : Chạy tự động bởi image timescale/timescaledb khi container khởi
--            tạo lần đầu (mount vào /docker-entrypoint-initdb.d), hoặc chạy
--            thủ công qua: psql -f 001_init.sql
-- =============================================================================

-- Bật extension TimescaleDB nếu image DB hỗ trợ (image timescale/timescaledb
-- đã cài sẵn extension này, IF NOT EXISTS để script vẫn chạy an toàn trên
-- một PostgreSQL thường không có extension - trong trường hợp đó các lệnh
-- create_hypertable() bên dưới sẽ được bọc trong kiểm tra tồn tại extension).
CREATE EXTENSION IF NOT EXISTS timescaledb;

-- -----------------------------------------------------------------------------
-- 1. Bảng klines — nến thực tế lấy từ Binance (REST bootstrap + WebSocket)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS klines (
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

-- Tạo hypertable trên open_time nếu TimescaleDB extension có sẵn.
-- Bọc trong DO block để migration không fail trên PostgreSQL thuần
-- (không có TimescaleDB) — khi đó bảng vẫn hoạt động như bảng thường.
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'timescaledb') THEN
        PERFORM create_hypertable('klines', 'open_time', if_not_exists => TRUE);
    END IF;
END $$;

-- Index phục vụ truy vấn phổ biến: lấy lịch sử nến theo symbol+interval,
-- sắp xếp/khoanh vùng theo thời gian (endpoint GET /api/v1/klines).
CREATE INDEX IF NOT EXISTS idx_klines_symbol_interval_open_time
    ON klines (symbol, interval, open_time DESC);

-- -----------------------------------------------------------------------------
-- 2. Bảng predictions — nến dự đoán (ghost candle) do Prediction Engine sinh ra
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS predictions (
    id              BIGSERIAL,
    symbol          TEXT NOT NULL,
    interval        TEXT NOT NULL,
    target_time     TIMESTAMPTZ NOT NULL,   -- thời điểm nến dự đoán sẽ đóng
    predicted_open  NUMERIC,
    predicted_high  NUMERIC,
    predicted_low   NUMERIC,
    predicted_close NUMERIC,
    confidence      NUMERIC,                -- 0..1
    model_version   TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (id, created_at)
);

-- Hypertable trên created_at (thời điểm dự đoán được tạo ra), theo đúng spec.
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'timescaledb') THEN
        PERFORM create_hypertable('predictions', 'created_at', if_not_exists => TRUE);
    END IF;
END $$;

-- Index phục vụ endpoint GET /api/v1/predictions/latest?symbol=...&interval=...
CREATE INDEX IF NOT EXISTS idx_predictions_symbol_interval_created_at
    ON predictions (symbol, interval, created_at DESC);

-- Index phụ trợ tra cứu theo target_time (khớp dự đoán với nến thực khi đóng nến).
CREATE INDEX IF NOT EXISTS idx_predictions_symbol_interval_target_time
    ON predictions (symbol, interval, target_time DESC);

-- -----------------------------------------------------------------------------
-- 3. Bảng accuracy_log — log độ chính xác (feedback loop tự học)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS accuracy_log (
    id              BIGSERIAL PRIMARY KEY,
    prediction_id   BIGINT,
    symbol          TEXT,
    interval        TEXT,
    actual_close    NUMERIC,
    predicted_close NUMERIC,
    error_pct       NUMERIC,
    accuracy_pct    NUMERIC,
    evaluated_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Index phục vụ endpoint GET /api/v1/accuracy?symbol=...&range=24h
CREATE INDEX IF NOT EXISTS idx_accuracy_log_symbol_interval_evaluated_at
    ON accuracy_log (symbol, interval, evaluated_at DESC);

-- Index tra cứu theo prediction_id (nối ngược lại bảng predictions).
CREATE INDEX IF NOT EXISTS idx_accuracy_log_prediction_id
    ON accuracy_log (prediction_id);

-- -----------------------------------------------------------------------------
-- 4. Bảng model_params_history — audit trail tối ưu hoá tham số (Genetic Algo)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS model_params_history (
    id           BIGSERIAL PRIMARY KEY,
    symbol       TEXT,
    params       JSONB,
    avg_accuracy NUMERIC,
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Index phục vụ tra cứu tham số mới nhất/tốt nhất theo symbol
-- (dùng cho rollback về params gần nhất có accuracy cao — circuit breaker).
CREATE INDEX IF NOT EXISTS idx_model_params_history_symbol_updated_at
    ON model_params_history (symbol, updated_at DESC);

-- =============================================================================
-- Hết migration 001_init.sql
-- =============================================================================
