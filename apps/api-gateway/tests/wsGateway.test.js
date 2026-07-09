'use strict';

const { test } = require('node:test');
const assert = require('node:assert/strict');
const http = require('node:http');
const { WebSocketServer, WebSocket } = require('ws');

process.env.DATABASE_URL = 'postgres://test:test@localhost:5432/test';

// Mock 'ioredis' TRƯỚC khi require gateway.js, để test không cần Redis thật.
// Mỗi instance được tạo ra (1 instance / subscription) được lưu lại để test
// có thể kiểm tra channel đã subscribe và việc quit() có được gọi khi cleanup.
const ioredisPath = require.resolve('ioredis');

class FakeRedis {
  constructor(url) {
    this.url = url;
    this.subscriptions = [];
    this.quitCalled = false;
    this._handlers = {};
    FakeRedis.instances.push(this);
  }

  on(event, cb) {
    this._handlers[event] = cb;
    return this;
  }

  removeAllListeners() {
    delete this._handlers.message;
  }

  async subscribe(...channels) {
    this.subscriptions.push(...channels);
    return channels.length;
  }

  async quit() {
    this.quitCalled = true;
  }

  // Mo phong 1 message pub/sub Redis thuc su den tu producer (ingestion-service/
  // prediction-engine).
  emitMessage(channel, message) {
    if (this._handlers.message) this._handlers.message(channel, message);
  }
}
FakeRedis.instances = [];

require.cache[ioredisPath] = { id: ioredisPath, filename: ioredisPath, loaded: true, exports: FakeRedis };

const attachWebSocketGateway = require('../src/ws/gateway');

function startTestServer() {
  const server = http.createServer();
  const wss = new WebSocketServer({ server, path: '/ws' });
  attachWebSocketGateway(wss);
  server.listen(0);
  return server;
}

function waitForMessage(ws) {
  return new Promise((resolve, reject) => {
    ws.once('message', (data) => {
      try {
        resolve(JSON.parse(data.toString()));
      } catch (err) {
        reject(err);
      }
    });
  });
}

function connect(server) {
  const { port } = server.address();
  const ws = new WebSocket(`ws://127.0.0.1:${port}/ws`);
  return new Promise((resolve, reject) => {
    ws.once('open', () => resolve(ws));
    ws.once('error', reject);
  });
}

test('ping trả về pong', async () => {
  FakeRedis.instances.length = 0;
  const server = startTestServer();
  try {
    const ws = await connect(server);
    const reply = waitForMessage(ws);
    ws.send(JSON.stringify({ action: 'ping' }));
    assert.deepEqual(await reply, { type: 'pong' });
    ws.close();
  } finally {
    server.close();
  }
});

test('subscribe mở subscriber Redis đúng channel', async () => {
  FakeRedis.instances.length = 0;
  const server = startTestServer();
  try {
    const ws = await connect(server);
    ws.send(JSON.stringify({ action: 'subscribe', symbol: 'BTCUSDT', interval: '1m' }));
    await new Promise((resolve) => setTimeout(resolve, 50));

    assert.equal(FakeRedis.instances.length, 1);
    assert.deepEqual(FakeRedis.instances[0].subscriptions, [
      'klines:BTCUSDT:1m',
      'predictions:BTCUSDT:1m',
      'accuracy:BTCUSDT:1m',
    ]);
    ws.close();
  } finally {
    server.close();
  }
});

test('unsubscribe đóng subscriber Redis cũ và trả ack', async () => {
  FakeRedis.instances.length = 0;
  const server = startTestServer();
  try {
    const ws = await connect(server);
    ws.send(JSON.stringify({ action: 'subscribe', symbol: 'BTCUSDT', interval: '1m' }));
    await new Promise((resolve) => setTimeout(resolve, 50));

    const reply = waitForMessage(ws);
    ws.send(JSON.stringify({ action: 'unsubscribe', symbol: 'BTCUSDT', interval: '1m' }));

    assert.deepEqual(await reply, { type: 'unsubscribed', data: { symbol: 'BTCUSDT', interval: '1m' } });
    assert.equal(FakeRedis.instances[0].quitCalled, true);
    ws.close();
  } finally {
    server.close();
  }
});

test('forward message tu Redis nguyen van, khong boc them 1 lop {type,data} nua', async () => {
  // Producer (ingestion-service/prediction-engine) da publish DUNG envelope
  // wire-format { type, data } theo asyncapi.yaml ngay tren Redis — gateway
  // chi duoc forward nguyen van, khong duoc tu suy type tu ten channel roi
  // wrap lai (bug thuc te da xay ra: client nhan {type,data:{type,data:{...}}}).
  FakeRedis.instances.length = 0;
  const server = startTestServer();
  try {
    const ws = await connect(server);
    ws.send(JSON.stringify({ action: 'subscribe', symbol: 'BTCUSDT', interval: '1m' }));
    await new Promise((resolve) => setTimeout(resolve, 50));

    const producerMessage = JSON.stringify({
      type: 'kline',
      data: { symbol: 'BTCUSDT', interval: '1m', close: 61800, isClosed: false },
    });

    const reply = waitForMessage(ws);
    FakeRedis.instances[0].emitMessage('klines:BTCUSDT:1m', producerMessage);

    const received = await reply;
    assert.deepEqual(received, JSON.parse(producerMessage));
    assert.equal(received.data.symbol, 'BTCUSDT');
    ws.close();
  } finally {
    server.close();
  }
});

test('action không hỗ trợ trả về lỗi', async () => {
  FakeRedis.instances.length = 0;
  const server = startTestServer();
  try {
    const ws = await connect(server);
    const reply = waitForMessage(ws);
    ws.send(JSON.stringify({ action: 'bogus' }));
    const message = await reply;
    assert.equal(message.type, 'error');
    ws.close();
  } finally {
    server.close();
  }
});
