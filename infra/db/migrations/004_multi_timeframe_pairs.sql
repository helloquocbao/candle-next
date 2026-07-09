-- =============================================================================
-- Migration: 004_multi_timeframe_pairs.sql
-- Muc dich : Them cac khung thoi gian gio/ngay/tuan/thang cho BTCUSDT va
--            ETHUSDT vao tracked_pairs, de ingestion-service/prediction-engine
--            tu dong fan-out theo dung co che da co san (xem
--            002_tracked_pairs.sql va resolve_tracked_pairs() o 2 service).
--            SOLUSDT giu nguyen 1m de han che so luong ket noi Binance/thread
--            dong thoi (moi cap la 1 WS connection + 1 PredictionEngine thread).
-- =============================================================================

INSERT INTO tracked_pairs (symbol, interval) VALUES
    ('BTCUSDT', '1h'),
    ('BTCUSDT', '1d'),
    ('BTCUSDT', '1w'),
    ('BTCUSDT', '1M'),
    ('ETHUSDT', '1h'),
    ('ETHUSDT', '1d'),
    ('ETHUSDT', '1w'),
    ('ETHUSDT', '1M')
ON CONFLICT (symbol, interval) DO NOTHING;

-- =============================================================================
-- Het migration 004_multi_timeframe_pairs.sql
-- =============================================================================
