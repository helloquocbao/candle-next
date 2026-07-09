-- =============================================================================
-- Migration: 005_market_column.sql
-- Mục đích : Hỗ trợ ĐA THỊ TRƯỜNG (crypto + chứng khoán HOSE) trên cùng schema.
--            Thêm cột `market` để phân biệt nguồn, MẶC ĐỊNH 'crypto' nên các
--            service crypto hiện tại KHÔNG cần sửa (INSERT bỏ qua cột này sẽ
--            tự nhận 'crypto'; các SELECT theo symbol/interval không đổi).
--            Service prediction-engine-hose ghi dữ liệu với market='hose'.
-- An toàn : Thuần additive (ADD COLUMN ... DEFAULT). Không đổi/không xoá gì
--            của crypto. Idempotent (IF NOT EXISTS) để chạy lại không lỗi.
-- =============================================================================

ALTER TABLE klines
    ADD COLUMN IF NOT EXISTS market TEXT NOT NULL DEFAULT 'crypto';

ALTER TABLE predictions
    ADD COLUMN IF NOT EXISTS market TEXT NOT NULL DEFAULT 'crypto';

-- Liệt kê nhanh symbol theo thị trường (endpoint GET /api/v1/symbols?market=).
CREATE INDEX IF NOT EXISTS idx_klines_market_symbol
    ON klines (market, symbol);

-- =============================================================================
-- Hết migration 005_market_column.sql
-- =============================================================================
