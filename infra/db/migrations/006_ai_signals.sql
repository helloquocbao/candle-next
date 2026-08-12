-- =============================================================================
-- Migration: 006_ai_signals.sql
-- Mục đích : Audit trail cho tín hiệu AI (DeepSeek, xem apps/prediction-engine/
--            src/ai_advisor.py và apps/prediction-engine-hose/src/ai_advisor.py)
--            được ensemble vào dự đoán bước t+1 (crypto) / phiên t+1 (HOSE).
--            Lưu tách biệt với `predictions` để:
--              1. Không đổi schema `predictions` hiện có (an toàn, additive).
--              2. Sau này so sánh accuracy_log của các prediction có/không có
--                 AI (lọc theo predictions.model_version LIKE '%+deepseek')
--                 để đánh giá khách quan AI có thực sự giúp cải thiện độ
--                 chính xác hay không, trước khi quyết định tăng DEEPSEEK_WEIGHT
--                 hay tắt hẳn tính năng.
-- An toàn  : Thuần tạo bảng mới (CREATE TABLE IF NOT EXISTS). Không đổi/không
--            xoá gì của các bảng hiện có. Idempotent, chạy lại không lỗi.
-- =============================================================================

CREATE TABLE IF NOT EXISTS ai_signals (
    id                    BIGSERIAL PRIMARY KEY,
    -- Tham chiếu bảng predictions (KHÔNG đặt FOREIGN KEY cứng vì predictions
    -- là hypertable với khoá chính composite (id, created_at) — tra cứu chéo
    -- khi cần thực hiện qua application code, không qua ràng buộc DB).
    prediction_id         BIGINT,
    symbol                TEXT NOT NULL,
    interval              TEXT NOT NULL,
    -- 'crypto' (mặc định, prediction-engine) | 'hose' (prediction-engine-hose).
    market                TEXT NOT NULL DEFAULT 'crypto',
    direction             TEXT NOT NULL,          -- 'up' | 'down' | 'flat'
    predicted_change_pct  NUMERIC,                 -- % thay đổi giá AI ước lượng
    ai_confidence         NUMERIC,                 -- 0..1, confidence GỐC của AI (trước blend)
    -- true nếu tín hiệu này ĐÃ được blend vào prediction tương ứng (hiện tại
    -- luôn true — cột này để dành cho hướng mở rộng sau: có thể ghi lại cả
    -- tín hiệu AI KHÔNG được áp dụng, vd để so sánh song song 2 chiến lược).
    blended               BOOLEAN NOT NULL DEFAULT TRUE,
    reasoning             TEXT,
    created_at            TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_ai_signals_symbol_interval_created_at
    ON ai_signals (symbol, interval, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_ai_signals_prediction_id
    ON ai_signals (prediction_id);

-- =============================================================================
-- Hết migration 006_ai_signals.sql
-- =============================================================================
