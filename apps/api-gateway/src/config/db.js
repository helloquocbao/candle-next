// Pool kết nối PostgreSQL/TimescaleDB dùng chung cho toàn bộ app
const { Pool, types } = require('pg');
const env = require('./env');

// Driver `pg` mặc định trả cột NUMERIC dạng STRING (để tránh mất độ chính xác
// float cho số tiền lớn) — nhưng client (frontend) cần number thật để vẽ
// chart/so sánh. OID 1700 = NUMERIC. Ép parse về Number ngay tại tầng DB để
// mọi route (klines/predictions/accuracy) tự động nhận đúng kiểu, không phải
// tự parseFloat rải rác ở từng route.
types.setTypeParser(1700, (value) => (value === null ? null : parseFloat(value)));

const pool = new Pool({
  connectionString: env.DATABASE_URL,
});

pool.on('error', (err) => {
  // eslint-disable-next-line no-console
  console.error('[db] Lỗi không mong muốn trên idle client của PostgreSQL pool:', err);
});

module.exports = pool;
