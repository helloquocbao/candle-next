// GET /api/v1/predictions/latest?symbol=&interval=
// Theo openapi.yaml: symbol (required), interval (required)
//
// Trả về dự đoán của CHU KỲ GẦN NHẤT (mỗi chu kỳ prediction-engine sinh
// PREDICTION_HORIZON dự đoán liên tiếp — multi-step forecast, xem
// prediction-engine::predict_next_n_candles). Dùng để frontend "seed" lại
// vùng giá dự đoán ngay khi load/đổi symbol-interval, thay vì phải đợi tới
// chu kỳ WS "prediction" MỚI tiếp theo — với khung ngày/tuần/tháng, chu kỳ
// mới có thể cách xa hàng giờ/ngày/tháng nếu chỉ dựa vào WS.
//
// LƯU Ý: không thể lọc đơn giản bằng "target_time >= now()" — vì các chu kỳ
// LIÊN TIẾP có target_time CHỒNG LẤN nhau (chu kỳ này dự đoán t+1..t+10, chu
// kỳ kế tiếp dự đoán (t+1)+1..(t+1)+10, nên (t+1)+1..t+10 bị dự đoán 2 lần ở
// 2 chu kỳ khác nhau). Phải lọc theo `created_at` của CHU KỲ MỚI NHẤT (gộp
// theo cửa sổ 30s vì 1 chu kỳ insert PREDICTION_HORIZON dòng liên tiếp,
// không cùng 1 created_at chính xác), không phải lọc theo target_time.
const express = require('express');
const pool = require('../config/db');

const router = express.Router();

router.get('/latest', async (req, res) => {
  const { symbol, interval } = req.query;

  if (!symbol || !interval) {
    return res.status(400).json({ error: 'Thiếu tham số bắt buộc: symbol, interval' });
  }

  try {
    const result = await pool.query(
      `WITH latest_cycle AS (
         SELECT MAX(created_at) AS created_at
         FROM predictions
         WHERE symbol = $1 AND interval = $2
       )
       SELECT p.id, p.symbol, p.interval, p.target_time,
              p.predicted_open, p.predicted_high, p.predicted_low, p.predicted_close,
              p.confidence, p.model_version, p.created_at
       FROM predictions p, latest_cycle
       WHERE p.symbol = $1 AND p.interval = $2
         AND latest_cycle.created_at IS NOT NULL
         AND p.created_at >= latest_cycle.created_at - INTERVAL '30 seconds'
       ORDER BY p.target_time ASC`,
      [symbol, interval]
    );

    return res.json({ symbol, interval, predictions: result.rows });
  } catch (err) {
    // eslint-disable-next-line no-console
    console.error('[routes/predictions] Lỗi truy vấn:', err);
    return res.status(500).json({ error: 'Lỗi truy vấn dữ liệu predictions' });
  }
});

module.exports = router;
