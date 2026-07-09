// GET /api/v1/accuracy?symbol=BTCUSDT&range=24h&interval=1m
// Theo project_technical_spec.md mục 5.1 & 3.2 (bảng accuracy_log)
//
// "interval" là optional (không có -> gộp accuracy của MỌI interval cùng
// symbol, giữ tương thích ngược). Từ khi 1 symbol có thể chạy song song
// nhiều interval (1m/1h/1d/1w/1M — xem tracked_pairs), FE cần lọc đúng
// interval đang xem để không trộn accuracy giữa các khung thời gian khác nhau.
const express = require('express');
const pool = require('../config/db');

const router = express.Router();

// Parse "range" đơn giản: hỗ trợ "1h", "24h", "7d" -> trả về số milliseconds
function parseRangeToMs(range) {
  const match = /^(\d+)(h|d)$/.exec((range || '').trim());
  if (!match) {
    return null;
  }
  const value = parseInt(match[1], 10);
  const unit = match[2];
  const unitMs = unit === 'h' ? 60 * 60 * 1000 : 24 * 60 * 60 * 1000;
  return value * unitMs;
}

router.get('/', async (req, res) => {
  const { symbol, interval } = req.query;
  const range = req.query.range || '24h';

  if (!symbol) {
    return res.status(400).json({ error: 'Thiếu tham số bắt buộc: symbol' });
  }

  const rangeMs = parseRangeToMs(range);
  if (rangeMs === null) {
    return res.status(400).json({ error: 'Tham số range không hợp lệ. Hỗ trợ: "1h", "24h", "7d"' });
  }

  const since = new Date(Date.now() - rangeMs);

  const conditions = ['symbol = $1', 'evaluated_at >= $2'];
  const params = [symbol, since];
  if (interval) {
    params.push(interval);
    conditions.push(`interval = $${params.length}`);
  }

  try {
    const result = await pool.query(
      `SELECT id, prediction_id, symbol, interval, actual_close, predicted_close,
              error_pct, accuracy_pct, open_time, evaluated_at
       FROM accuracy_log
       WHERE ${conditions.join(' AND ')}
       ORDER BY evaluated_at DESC`,
      params
    );

    const samples = result.rows;
    const count = samples.length;
    const avgAccuracy =
      count > 0
        ? samples.reduce((sum, row) => sum + Number(row.accuracy_pct || 0), 0) / count
        : null;

    return res.json({
      avg_accuracy: avgAccuracy,
      count,
      samples,
    });
  } catch (err) {
    // eslint-disable-next-line no-console
    console.error('[routes/accuracy] Lỗi truy vấn:', err);
    return res.status(500).json({ error: 'Lỗi truy vấn dữ liệu accuracy_log' });
  }
});

module.exports = router;
module.exports.parseRangeToMs = parseRangeToMs;
