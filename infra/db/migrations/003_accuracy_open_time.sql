-- =============================================================================
-- Migration: 003_accuracy_open_time.sql
-- Muc dich : Them cot open_time vao accuracy_log — luu lai chinh xac nen THAT
--            nao da duoc danh gia (khop voi prediction nao), de frontend co
--            the ve marker % chinh xac ngay tren nen do (dac biet quan trong
--            voi khung thoi gian dai — ngay/tuan/thang — noi nen dong rat
--            thua, can hien thi lai duoc lich su khi F5 lai trang thay vi chi
--            dua vao WS accuracy_update realtime).
-- =============================================================================

ALTER TABLE accuracy_log
    ADD COLUMN IF NOT EXISTS open_time TIMESTAMPTZ;

-- Phuc vu truy van "danh sach accuracy theo symbol+interval, sap theo thoi
-- gian nen" (dung de seed marker khi frontend load lai trang).
CREATE INDEX IF NOT EXISTS idx_accuracy_log_symbol_interval_open_time
    ON accuracy_log (symbol, interval, open_time DESC);

-- =============================================================================
-- Het migration 003_accuracy_open_time.sql
-- =============================================================================
