'use strict';

const { Pool } = require('pg');

let pool = null;

/**
 * Khoi tao (hoac tra ve) pool ket noi Postgres/TimescaleDB dung chung
 * cho ca service. DATABASE_URL doc tu bien moi truong.
 */
function getPool() {
  if (pool) return pool;

  const connectionString = process.env.DATABASE_URL;
  if (!connectionString) {
    console.error(
      '[db] Canh bao: bien moi truong DATABASE_URL chua duoc thiet lap. ' +
        'Cac thao tac ghi DB se that bai cho toi khi duoc cau hinh dung.'
    );
  }

  pool = new Pool({ connectionString });

  pool.on('error', (err) => {
    // Loi tren idle client khong duoc de crash toan bo process.
    console.error('[db] Loi khong mong muon tren Postgres pool (idle client):', err.message);
  });

  return pool;
}

/**
 * Ghi (upsert) mot nen da dong (isClosed = true) vao bang `klines`.
 * Nen dang hinh thanh (isClosed = false) se KHONG duoc ghi vao DB —
 * chi publish qua Redis de FE render "ghost/forming candle".
 *
 * Schema:
 * CREATE TABLE klines (
 *   symbol TEXT, interval TEXT, open_time TIMESTAMPTZ,
 *   open NUMERIC, high NUMERIC, low NUMERIC, close NUMERIC, volume NUMERIC,
 *   close_time TIMESTAMPTZ,
 *   PRIMARY KEY (symbol, interval, open_time)
 * );
 *
 * @param {Object} kline - object da chuan hoa tu klineNormalizer
 * @returns {Promise<boolean>} true neu ghi thanh cong, false neu bi bo qua/loi
 */
async function insertKline(kline) {
  if (!kline || kline.isClosed !== true) {
    // Chi ghi DB khi nen da dong hoan toan.
    return false;
  }

  const query = `
    INSERT INTO klines (symbol, interval, open_time, open, high, low, close, volume, close_time)
    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
    ON CONFLICT (symbol, interval, open_time)
    DO UPDATE SET
      open = EXCLUDED.open,
      high = EXCLUDED.high,
      low = EXCLUDED.low,
      close = EXCLUDED.close,
      volume = EXCLUDED.volume,
      close_time = EXCLUDED.close_time;
  `;

  const values = [
    kline.symbol,
    kline.interval,
    kline.openTime,
    kline.open,
    kline.high,
    kline.low,
    kline.close,
    kline.volume,
    kline.closeTime,
  ];

  try {
    const db = getPool();
    await db.query(query, values);
    return true;
  } catch (err) {
    console.error(
      `[db] Loi khi ghi kline vao DB (${kline.symbol} ${kline.interval} ${kline.openTime}):`,
      err.message
    );
    // Khong throw — service phai tiep tuc chay, chi log loi.
    return false;
  }
}

/**
 * Doc danh sach cap symbol/interval dang active tu bang tracked_pairs
 * (infra/db/migrations/002_tracked_pairs.sql) - nguon chan ly chung de
 * ingestion-service/prediction-engine/api-gateway deu fan-out/hien thi
 * dung mot danh sach, khong hardcode rieng moi noi.
 */
async function getTrackedPairs() {
  const db = getPool();
  const result = await db.query(
    'SELECT symbol, interval FROM tracked_pairs WHERE is_active ORDER BY symbol, interval'
  );
  return result.rows;
}

/**
 * Dong pool ket noi (dung khi shutdown graceful).
 */
async function closePool() {
  if (pool) {
    try {
      await pool.end();
    } catch (err) {
      console.error('[db] Loi khi dong Postgres pool:', err.message);
    } finally {
      pool = null;
    }
  }
}

module.exports = {
  getPool,
  insertKline,
  getTrackedPairs,
  closePool,
};
