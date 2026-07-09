const express = require('express');
const http = require('http');
const { WebSocketServer } = require('ws');

const env = require('./config/env');
const pool = require('./config/db');
const corsMiddleware = require('./middleware/cors');
const rateLimit = require('./middleware/rateLimit');
const attachWebSocketGateway = require('./ws/gateway');

const klinesRouter = require('./routes/klines');
const predictionsRouter = require('./routes/predictions');
const accuracyRouter = require('./routes/accuracy');
const symbolsRouter = require('./routes/symbols');

const app = express();

app.use(express.json());

// Health check cho load balancer — không cần rate limit/cors riêng
app.get('/health', (req, res) => {
  res.json({ status: 'ok' });
});

// Mount rateLimit + cors TRƯỚC routes, áp dụng cho toàn bộ /api/*
app.use('/api', corsMiddleware, rateLimit);

// Đăng ký routes dưới prefix /api/v1 theo đúng openapi.yaml
app.use('/api/v1/klines', klinesRouter);
app.use('/api/v1/predictions', predictionsRouter);
app.use('/api/v1/accuracy', accuracyRouter);
app.use('/api/v1/symbols', symbolsRouter);

// 404 fallback
app.use((req, res) => {
  res.status(404).json({ error: 'Not found' });
});

// Global error handler — bắt lỗi từ middleware (vd CORS callback(new Error(...)))
// và mọi lỗi được next(err) từ route, đảm bảo response luôn là JSON, không rơi
// về trang lỗi HTML mặc định của Express.
// eslint-disable-next-line no-unused-vars
app.use((err, req, res, next) => {
  // eslint-disable-next-line no-console
  console.error('[index] Lỗi không được xử lý:', err);
  if (res.headersSent) return next(err);
  res.status(err.status || 500).json({ error: err.message || 'Internal server error' });
});

// Tạo http.Server từ Express app để WebSocketServer có thể gắn lên cùng port
const server = http.createServer(app);

// Gắn WebSocketServer lên cùng server tại path "/ws" — khớp với location
// "/ws/" đã cấu hình sẵn trong infra/docker/nginx/default.conf, để reverse
// proxy tách rõ traffic WebSocket khỏi traffic phục vụ frontend ở path gốc "/".
const wss = new WebSocketServer({ server, path: '/ws' });
attachWebSocketGateway(wss);

server.listen(env.API_PORT, () => {
  // eslint-disable-next-line no-console
  console.log(`[api-gateway] Đang lắng nghe tại port ${env.API_PORT}`);
});

// Graceful shutdown: đóng HTTP server (không nhận request mới, chờ request
// đang xử lý xong), đóng toàn bộ WebSocket connection, rồi đóng DB pool.
// Docker/K8s gửi SIGTERM khi stop container — nếu không xử lý, các request/WS
// đang mở sẽ bị cắt ngang đột ngột.
let shuttingDown = false;

function gracefulShutdown(signal) {
  if (shuttingDown) return;
  shuttingDown = true;

  // eslint-disable-next-line no-console
  console.log(`[api-gateway] Nhận tín hiệu ${signal}, đang tắt...`);

  const forceExitTimer = setTimeout(() => {
    // eslint-disable-next-line no-console
    console.error('[api-gateway] Không tắt sạch được trong thời gian cho phép, buộc thoát.');
    process.exit(1);
  }, 10_000);

  server.close(() => {
    wss.clients.forEach((client) => client.terminate());

    pool.end()
      .catch((err) => {
        // eslint-disable-next-line no-console
        console.error('[api-gateway] Lỗi khi đóng DB pool:', err);
      })
      .finally(() => {
        clearTimeout(forceExitTimer);
        // eslint-disable-next-line no-console
        console.log('[api-gateway] Đã tắt sạch sẽ.');
        process.exit(0);
      });
  });
}

process.on('SIGTERM', () => gracefulShutdown('SIGTERM'));
process.on('SIGINT', () => gracefulShutdown('SIGINT'));

module.exports = server;
