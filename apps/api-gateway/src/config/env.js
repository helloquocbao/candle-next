// Đọc cấu hình từ biến môi trường (.env khi chạy local)
require('dotenv').config();

if (!process.env.DATABASE_URL) {
  throw new Error('Thiếu biến môi trường bắt buộc: DATABASE_URL');
}

const env = {
  DATABASE_URL: process.env.DATABASE_URL,
  REDIS_URL: process.env.REDIS_URL || 'redis://localhost:6379',
  API_PORT: parseInt(process.env.API_PORT, 10) || 8080,
  // Nhiều origin phân cách dấu phẩy, vd: "http://localhost:3000,https://app.example.com"
  CORS_ORIGIN: process.env.CORS_ORIGIN || '*',
};

module.exports = env;
