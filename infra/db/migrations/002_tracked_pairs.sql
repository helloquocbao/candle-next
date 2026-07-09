-- =============================================================================
-- Migration: 002_tracked_pairs.sql
-- Mục đích : Bảng cấu hình symbol/interval mà toàn hệ thống theo dõi, thay cho
--            danh sách hardcode trong api-gateway/ingestion-service/prediction-engine.
--            Đây là nguồn chân lý duy nhất để thêm/bớt cặp coin theo dõi mà
--            không cần sửa code hay đổi biến môi trường ở từng service.
-- =============================================================================

CREATE TABLE IF NOT EXISTS tracked_pairs (
    symbol     TEXT NOT NULL,
    interval   TEXT NOT NULL,
    is_active  BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (symbol, interval)
);

-- Index phục vụ truy vấn phổ biến: lấy danh sách cặp đang active
-- (api-gateway GET /api/v1/symbols, ingestion-service/prediction-engine khi khởi động).
CREATE INDEX IF NOT EXISTS idx_tracked_pairs_active
    ON tracked_pairs (is_active);

-- Seed 3 cặp mặc định theo đúng danh sách đã hardcode trước đây.
INSERT INTO tracked_pairs (symbol, interval) VALUES
    ('BTCUSDT', '1m'),
    ('ETHUSDT', '1m'),
    ('SOLUSDT', '1m')
ON CONFLICT (symbol, interval) DO NOTHING;

-- =============================================================================
-- Hết migration 002_tracked_pairs.sql
-- =============================================================================
