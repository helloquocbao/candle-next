'use strict';

require('dotenv').config();

const { getExchangeAdapter, DEFAULT_EXCHANGE } = require('./exchanges');
const { insertKline, getTrackedPairs, closePool } = require('./db');
const { publishKlineUpdate, closeRedisClient } = require('./redisPublisher');
const { resolveTrackedPairs } = require('./trackedPairs');

const BOOTSTRAP_LIMIT = Number(process.env.BOOTSTRAP_LIMIT) || 500;

/**
 * Chon san (exchange) cho 1 cap: uu tien field `exchange` cua cap (vd tu
 * SYMBOL_PAIRS "BTCUSDT:1m:okx"), roi env.EXCHANGE, cuoi cung mac dinh.
 */
function resolveExchangeName(pair) {
  return (pair.exchange || process.env.EXCHANGE || DEFAULT_EXCHANGE).toLowerCase();
}

/**
 * Buoc 1: Bootstrap lich su qua REST — lay N nen gan nhat (da chuan hoa boi
 * adapter cua san tuong ung), ghi vao DB (upsert) de co du lieu nen tang cho
 * prediction engine truoc khi WebSocket real-time bat dau chay.
 */
async function bootstrapHistory(adapter, symbol, interval) {
  console.log(
    `[index] Bootstrap lich su ${BOOTSTRAP_LIMIT} nen cho ${symbol} ${interval} qua ${adapter.name} REST...`
  );

  try {
    const normalizedKlines = await adapter.fetchHistory({
      symbol,
      interval,
      limit: BOOTSTRAP_LIMIT,
    });

    if (!normalizedKlines.length) {
      console.error(
        `[index] Khong lay duoc du lieu lich su tu ${adapter.name} cho ${symbol} ${interval} (mang rong). ` +
          'Se tiep tuc khoi dong WebSocket real-time, du lieu se duoc bu dan.'
      );
      return;
    }

    let insertedCount = 0;
    for (const normalized of normalizedKlines) {
      try {
        const ok = await insertKline(normalized);
        if (ok) insertedCount += 1;
      } catch (err) {
        console.error(`[index] Loi khi xu ly 1 nen lich su (${symbol} ${interval}):`, err.message);
      }
    }

    console.log(
      `[index] Bootstrap ${symbol} ${interval} hoan tat: ${insertedCount}/${normalizedKlines.length} nen da duoc ghi/cap nhat vao DB.`
    );
  } catch (err) {
    console.error(
      `[index] Loi khong mong muon trong qua trinh bootstrap lich su (${symbol} ${interval}):`,
      err.message
    );
    // Khong throw — van tiep tuc mo WebSocket real-time du bootstrap that bai.
  }
}

/**
 * Buoc 2: Mo ket noi WebSocket real-time (qua adapter cua san). Voi moi nen
 * DA CHUAN HOA nhan duoc:
 * - Publish MOI update (ke ca nen dang hinh thanh) len Redis.
 * - Chi ghi vao DB khi nen da dong (isClosed = true).
 *
 * @returns {{ close: () => void }} handle de dong stream khi shutdown
 */
function startRealtimeStream(adapter, symbol, interval) {
  console.log(`[index] Khoi dong WebSocket real-time (${adapter.name}) cho ${symbol} ${interval}...`);

  return adapter.connectStream({
    symbol,
    interval,
    onKline: async (normalized) => {
      // Publish moi update (ca nen dang hinh thanh) len Redis cho FE ve real-time.
      try {
        await publishKlineUpdate(normalized);
      } catch (err) {
        console.error(`[index] Loi khi publish kline len Redis (${symbol} ${interval}):`, err.message);
      }

      // Chi ghi DB khi nen da dong hoan toan.
      if (normalized.isClosed) {
        try {
          await insertKline(normalized);
        } catch (err) {
          console.error(`[index] Loi khi ghi kline da dong vao DB (${symbol} ${interval}):`, err.message);
        }
      }
    },
  });
}

async function runPair(symbol, interval, exchangeName) {
  const adapter = getExchangeAdapter(exchangeName);
  await bootstrapHistory(adapter, symbol, interval);
  return startRealtimeStream(adapter, symbol, interval);
}

// Handle cua tat ca stream dang chay, dung de dong sach khi shutdown.
let activeStreams = [];

async function main() {
  const pairs = await resolveTrackedPairs({ getTrackedPairsFromDb: getTrackedPairs });

  console.log(
    `[index] Khoi dong ingestion-service cho ${pairs.length} cap: ` +
      pairs
        .map((pair) => `${pair.symbol}/${pair.interval}@${resolveExchangeName(pair)}`)
        .join(', ')
  );

  activeStreams = await Promise.all(
    pairs.map((pair) => runPair(pair.symbol, pair.interval, resolveExchangeName(pair)))
  );
}

// Xu ly shutdown graceful (Docker/K8s se gui SIGTERM khi stop container).
async function shutdown(signal) {
  console.log(`[index] Nhan tin hieu ${signal}, dang dong cac ket noi...`);
  try {
    activeStreams.forEach((stream) => stream && stream.close());
    await closeRedisClient();
    await closePool();
  } catch (err) {
    console.error('[index] Loi khi dong ket noi trong qua trinh shutdown:', err.message);
  } finally {
    process.exit(0);
  }
}

process.on('SIGINT', () => shutdown('SIGINT'));
process.on('SIGTERM', () => shutdown('SIGTERM'));

// Bao ve process khoi crash do loi khong bat duoc — chi log, khong throw tiep.
process.on('unhandledRejection', (reason) => {
  console.error('[index] Unhandled promise rejection:', reason);
});
process.on('uncaughtException', (err) => {
  console.error('[index] Uncaught exception:', err);
});

main().catch((err) => {
  console.error('[index] Loi fatal khi khoi dong service:', err.message);
  // Khong process.exit(1) ngay — de container/orchestrator co the quyet dinh
  // restart policy; nhung log ro de de debug.
});
