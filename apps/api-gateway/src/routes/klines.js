// GET /api/v1/klines?symbol=&interval=&limit=500
// Theo openapi.yaml: symbol (required), interval (required), limit (default 500)
const express = require('express');
const pool = require('../config/db');

const router = express.Router();

// Interval hợp lệ theo chuẩn Binance klines mà ingestion-service hỗ trợ.
const VALID_INTERVALS = new Set([
  '1m', '3m', '5m', '15m', '30m',
  '1h', '2h', '4h', '6h', '8h', '12h',
  '1d', '3d', '1w', '1M',
]);
const MAX_LIMIT = 1000;
const DEFAULT_LIMIT = 500;

router.get('/', async (req, res) => {
  const { symbol, interval } = req.query;

  if (!symbol || !interval) {
    return res.status(400).json({ error: 'Thiếu tham số bắt buộc: symbol, interval' });
  }

  if (!VALID_INTERVALS.has(interval)) {
    return res.status(400).json({ error: `interval không hợp lệ: ${interval}` });
  }

  const rawLimit = parseInt(req.query.limit, 10);
  if (req.query.limit !== undefined && (Number.isNaN(rawLimit) || rawLimit <= 0)) {
    return res.status(400).json({ error: 'limit phải là số nguyên dương' });
  }
  const limit = Math.min(rawLimit || DEFAULT_LIMIT, MAX_LIMIT);

  try {
    let result = await pool.query(
      `SELECT symbol, interval, open_time, open, high, low, close, volume, close_time
       FROM klines
       WHERE symbol = $1 AND interval = $2
       ORDER BY open_time DESC
       LIMIT $3`,
      [symbol, interval, limit]
    );

    if (result.rows.length === 0 && (interval === '1w' || interval === '1M')) {
      const truncUnit = interval === '1w' ? 'week' : 'month';
      result = await pool.query(
        `SELECT 
           $1::text AS symbol,
           $2::text AS interval,
           date_trunc($3, open_time) AS open_time,
           (array_agg(open ORDER BY open_time ASC))[1] AS open,
           MAX(high) AS high,
           MIN(low) AS low,
           (array_agg(close ORDER BY open_time DESC))[1] AS close,
           SUM(volume) AS volume,
           date_trunc($3, open_time) AS close_time
         FROM klines
         WHERE symbol = $1 AND interval = '1d'
         GROUP BY date_trunc($3, open_time)
         ORDER BY open_time DESC
         LIMIT $4`,
        [symbol, interval, truncUnit, limit]
      );
    }

    return res.json(result.rows);
  } catch (err) {
    // eslint-disable-next-line no-console
    console.error('[routes/klines] Lỗi truy vấn:', err);
    return res.status(500).json({ error: 'Lỗi truy vấn dữ liệu klines' });
  }
});

module.exports = router;
