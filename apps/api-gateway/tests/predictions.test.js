'use strict';

const { test } = require('node:test');
const assert = require('node:assert/strict');
const http = require('node:http');

const express = require('express');

process.env.DATABASE_URL = 'postgres://test:test@localhost:5432/test';

const dbPath = require.resolve('../src/config/db');

const mockPool = { query: async () => ({ rows: [] }) };
require.cache[dbPath] = { id: dbPath, filename: dbPath, loaded: true, exports: mockPool };

const predictionsRouter = require('../src/routes/predictions');

function startTestServer() {
  const app = express();
  app.use('/predictions', predictionsRouter);
  return app.listen(0);
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

test('GET /predictions/latest requires symbol and interval', async () => {
  const server = startTestServer();
  try {
    const res = await get(server, '/predictions/latest');
    assert.equal(res.status, 400);
  } finally {
    server.close();
  }
});

test('GET /predictions/latest tra ve mang predictions rong khi chua co du doan', async () => {
  mockPool.query = async () => ({ rows: [] });
  const server = startTestServer();
  try {
    const res = await get(server, '/predictions/latest?symbol=BTCUSDT&interval=1d');
    assert.equal(res.status, 200);
    assert.deepEqual(res.body, { symbol: 'BTCUSDT', interval: '1d', predictions: [] });
  } finally {
    server.close();
  }
});

test('GET /predictions/latest loc theo chu ky created_at gan nhat, sap tang dan theo target_time', async () => {
  let capturedSql;
  let capturedParams;
  const rows = [
    { target_time: '2026-01-01T00:01:00.000Z', predicted_close: 101 },
    { target_time: '2026-01-01T00:02:00.000Z', predicted_close: 102 },
  ];
  mockPool.query = async (sql, params) => {
    capturedSql = sql;
    capturedParams = params;
    return { rows };
  };
  const server = startTestServer();
  try {
    const res = await get(server, '/predictions/latest?symbol=BTCUSDT&interval=1m');
    assert.equal(res.status, 200);
    assert.match(capturedSql, /MAX\(created_at\)/);
    assert.match(capturedSql, /INTERVAL '30 seconds'/);
    assert.match(capturedSql, /ORDER BY p\.target_time ASC/);
    assert.deepEqual(capturedParams, ['BTCUSDT', '1m']);
    assert.deepEqual(res.body.predictions, rows);
  } finally {
    server.close();
  }
});

test('GET /predictions/latest tra 500 khi query loi', async () => {
  mockPool.query = async () => { throw new Error('boom'); };
  const server = startTestServer();
  try {
    const res = await get(server, '/predictions/latest?symbol=BTCUSDT&interval=1m');
    assert.equal(res.status, 500);
  } finally {
    server.close();
  }
});
