// GET /api/v1/symbols — danh sách cặp coin đang được hệ thống theo dõi
// Nguồn dữ liệu: bảng tracked_pairs (infra/db/migrations/002_tracked_pairs.sql),
// cũng là bảng mà ingestion-service/prediction-engine đọc để biết cần fan-out
// theo dõi những symbol/interval nào.
const express = require('express');
const pool = require('../config/db');

const router = express.Router();

router.get('/', async (req, res) => {
  const { market } = req.query;

  try {
    // Có ?market= -> liệt kê symbol theo thị trường từ bảng klines (cột
    // market thêm ở migration 005). Dùng cho toggle Crypto/CK VN ở frontend.
    // KHÔNG có param -> giữ nguyên hành vi cũ (danh sách tracked_pairs crypto)
    // để không phá client hiện tại.
    if (market) {
      const result = await pool.query(
        'SELECT DISTINCT symbol FROM klines WHERE market = $1 ORDER BY symbol',
        [market]
      );
      return res.json(result.rows.map((row) => row.symbol));
    }

    const result = await pool.query(
      'SELECT DISTINCT symbol FROM tracked_pairs WHERE is_active ORDER BY symbol'
    );
    return res.json(result.rows.map((row) => row.symbol));
  } catch (err) {
    // eslint-disable-next-line no-console
    console.error('[routes/symbols] Lỗi truy vấn:', err);
    return res.status(500).json({ error: 'Lỗi truy vấn danh sách symbol' });
  }
});

module.exports = router;
