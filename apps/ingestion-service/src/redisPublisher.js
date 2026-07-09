'use strict';

const Redis = require('ioredis');

let redisClient = null;

/**
 * Khoi tao (hoac tra ve) client Redis dung chung cho ca service.
 * REDIS_URL doc tu bien moi truong.
 */
function getRedisClient() {
  if (redisClient) return redisClient;

  const redisUrl = process.env.REDIS_URL || 'redis://localhost:6379';

  redisClient = new Redis(redisUrl, {
    retryStrategy(times) {
      // Backoff tang dan, toi da 10s giua cac lan retry cua ioredis.
      const delay = Math.min(times * 1000, 10000);
      console.error(`[redisPublisher] Mat ket noi Redis, thu lai lan ${times} sau ${delay}ms...`);
      return delay;
    },
    maxRetriesPerRequest: null,
  });

  redisClient.on('connect', () => {
    console.log('[redisPublisher] Da ket noi toi Redis.');
  });

  redisClient.on('error', (err) => {
    console.error('[redisPublisher] Loi ket noi Redis:', err.message);
  });

  return redisClient;
}

/**
 * Publish MOI update cua nen (ke ca nen dang hinh thanh, khong chi khi dong)
 * len channel `klines:<symbol>:<interval>`.
 *
 * Payload tuan theo asyncapi.yaml — channel "kline", message "klineUpdate":
 * { "type": "kline", "data": { ...normalized kline... } }
 *
 * @param {Object} kline - object da chuan hoa tu klineNormalizer
 */
async function publishKlineUpdate(kline) {
  if (!kline || !kline.symbol || !kline.interval) {
    console.error('[redisPublisher] Bo qua publish: kline khong hop le.', kline);
    return;
  }

  const channel = `klines:${kline.symbol}:${kline.interval}`;
  const message = JSON.stringify({
    type: 'kline',
    data: kline,
  });

  try {
    const client = getRedisClient();
    await client.publish(channel, message);
  } catch (err) {
    console.error(`[redisPublisher] Loi khi publish len channel "${channel}":`, err.message);
    // Khong throw — bo qua lan publish nay, cac update sau van tiep tuc.
  }
}

/**
 * Dong ket noi Redis (dung khi shutdown graceful).
 */
async function closeRedisClient() {
  if (redisClient) {
    try {
      await redisClient.quit();
    } catch (err) {
      console.error('[redisPublisher] Loi khi dong ket noi Redis:', err.message);
    } finally {
      redisClient = null;
    }
  }
}

module.exports = {
  getRedisClient,
  publishKlineUpdate,
  closeRedisClient,
};
