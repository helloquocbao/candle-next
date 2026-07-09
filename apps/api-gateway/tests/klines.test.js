'use strict';

const { test } = require('node:test');
const assert = require('node:assert/strict');
const http = require('node:http');

const express = require('express');

// klines.js require ../config/db -> ../config/env, và env.js giờ throw nếu
// thiếu DATABASE_URL. Set giá trị giả TRƯỚC khi require bất cứ thứ gì liên
// quan, vì test này không thực sự kết nối DB (query() đã được mock bên dưới).
process.env.DATABASE_URL = 'postgres://test:test@localhost:5432/test';

// Mock module '../config/db' TRƯỚC khi require route, để route không thử
// kết nối Postgres thật khi chạy test.
const dbPath = require.resolve('../src/config/db');

const mockPool = {
  query: async () => ({ rows: [{ symbol: 'BTCUSDT', interval: '1m', close: 100 }] }),
};
require.cache[dbPath] = { id: dbPath, filename: dbPath, loaded: true, exports: mockPool };

const klinesRouter = require('../src/routes/klines');

function startTestServer() {
  const app = express();
  app.use('/klines', klinesRouter);
  const server = app.listen(0);
  return server;
}

function get(server, path) {
  return new Promise((resolve, reject) => {
    const { port } = server.address();
    http.get(`http://127.0.0.1:${port}${path}`, (res) => {
      let body = '';
      res.on('data', (chunk) => { body += chunk; });
      res.on('end', () => resolve({ status: res.statusCode, body: JSON.parse(body) }));
    }).on('error', reject);
  });
}

test('GET /klines requires symbol and interval', async () => {
  const server = startTestServer();
  try {
    const res = await get(server, '/klines');
    assert.equal(res.status, 400);
  } finally {
    server.close();
  }
});

test('GET /klines rejects invalid interval', async () => {
  const server = startTestServer();
  try {
    const res = await get(server, '/klines?symbol=BTCUSDT&interval=7x');
    assert.equal(res.status, 400);
  } finally {
    server.close();
  }
});

test('GET /klines rejects non-positive limit', async () => {
  const server = startTestServer();
  try {
    const res = await get(server, '/klines?symbol=BTCUSDT&interval=1m&limit=-5');
    assert.equal(res.status, 400);
  } finally {
    server.close();
  }
});

test('GET /klines succeeds with valid params', async () => {
  const server = startTestServer();
  try {
    const res = await get(server, '/klines?symbol=BTCUSDT&interval=1m&limit=10');
    assert.equal(res.status, 200);
    assert.ok(Array.isArray(res.body));
  } finally {
    server.close();
  }
});
