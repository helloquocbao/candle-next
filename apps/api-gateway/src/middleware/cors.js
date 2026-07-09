// CORS middleware với origin whitelist đọc từ env CORS_ORIGIN (phân cách dấu phẩy)
const cors = require('cors');
const env = require('../config/env');

function buildCorsMiddleware() {
  if (env.CORS_ORIGIN === '*') {
    return cors({ origin: '*' });
  }

  const whitelist = env.CORS_ORIGIN.split(',')
    .map((origin) => origin.trim())
    .filter(Boolean);

  return cors({
    origin(origin, callback) {
      // Cho phép request không có origin (vd: curl, server-to-server, mobile app)
      if (!origin || whitelist.includes(origin)) {
        callback(null, true);
      } else {
        callback(new Error(`CORS: origin "${origin}" không nằm trong whitelist`));
      }
    },
  });
}

module.exports = buildCorsMiddleware();
