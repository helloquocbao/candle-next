// Rate limit áp dụng cho toàn bộ /api/* để tránh lạm dụng
const rateLimit = require('express-rate-limit');

const apiRateLimit = rateLimit({
  windowMs: 60 * 1000, // 1 phút
  max: 120, // tối đa 120 request/phút/IP
  standardHeaders: true,
  legacyHeaders: false,
  message: { error: 'Quá nhiều request, vui lòng thử lại sau.' },
});

module.exports = apiRateLimit;
