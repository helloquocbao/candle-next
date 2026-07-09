'use strict';

const { test } = require('node:test');
const assert = require('node:assert/strict');
const http = require('node:http');

const express = require('express');

process.env.DATABASE_URL = 'postgres://test:test@localhost:5432/test';

const dbPath = require.resolve('../src/config/db');

const mockPool = {
  query: async () => ({
    rows: [{ symbol: 'BTCUSDT' }, { symbol: 'ETHUSDT' }, { symbol: 'SOLUSDT' }],
  }),
};
require.cache[dbPath] = { id: dbPath, filename: dbPath, loaded: true, exports: mockPool };

const symbolsRouter = require('../src/routes/symbols');

function startTestServer() {
  const app = express();
  app.use('/symbols', symbolsRouter);
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

test('GET /symbols trả về danh sách symbol từ DB (chuỗi phẳng, không phải object)', async () => {
  const server = startTestServer();
  try {
    const res = await get(server, '/symbols');
    assert.equal(res.status, 200);
    assert.deepEqual(res.body, ['BTCUSDT', 'ETHUSDT', 'SOLUSDT']);
  } finally {
    server.close();
  }
});

test('GET /symbols trả 500 khi query lỗi', async () => {
  mockPool.query = async () => { throw new Error('boom'); };
  const server = startTestServer();
  try {
    const res = await get(server, '/symbols');
    assert.equal(res.status, 500);
  } finally {
    server.close();
  }
});
