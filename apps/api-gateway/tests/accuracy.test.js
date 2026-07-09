'use strict';

const { test } = require('node:test');
const assert = require('node:assert/strict');
const http = require('node:http');

const express = require('express');

// accuracy.js require ../config/db -> ../config/env, env.js throw nếu thiếu
// DATABASE_URL. Set giá trị giả — test này không kết nối DB thật.
process.env.DATABASE_URL = 'postgres://test:test@localhost:5432/test';

const dbPath = require.resolve('../src/config/db');

const mockPool = { query: async () => ({ rows: [] }) };
require.cache[dbPath] = { id: dbPath, filename: dbPath, loaded: true, exports: mockPool };

const accuracyRouter = require('../src/routes/accuracy');
const { parseRangeToMs } = accuracyRouter;

function startTestServer() {
  const app = express();
  app.use('/accuracy', accuracyRouter);
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

test('GET /accuracy khong loc interval khi khong truyen param', async () => {
  let capturedParams;
  mockPool.query = async (_sql, params) => { capturedParams = params; return { rows: [] }; };
  const server = startTestServer();
  try {
    const res = await get(server, '/accuracy?symbol=BTCUSDT');
    assert.equal(res.status, 200);
    assert.deepEqual(capturedParams.length, 2);
  } finally {
    server.close();
  }
});

test('GET /accuracy loc theo interval khi co truyen param', async () => {
  let capturedSql;
  let capturedParams;
  mockPool.query = async (sql, params) => {
    capturedSql = sql;
    capturedParams = params;
    return { rows: [] };
  };
  const server = startTestServer();
  try {
    const res = await get(server, '/accuracy?symbol=BTCUSDT&interval=1d');
    assert.equal(res.status, 200);
    assert.match(capturedSql, /interval = \$3/);
    assert.deepEqual(capturedParams, ['BTCUSDT', capturedParams[1], '1d']);
  } finally {
    server.close();
  }
});

test('parseRangeToMs parses hours correctly', () => {
  assert.equal(parseRangeToMs('24h'), 24 * 60 * 60 * 1000);
});

test('parseRangeToMs parses days correctly', () => {
  assert.equal(parseRangeToMs('7d'), 7 * 24 * 60 * 60 * 1000);
});

test('parseRangeToMs returns null for invalid input', () => {
  assert.equal(parseRangeToMs('abc'), null);
  assert.equal(parseRangeToMs(''), null);
  assert.equal(parseRangeToMs('24x'), null);
});

test('parseRangeToMs trims whitespace', () => {
  assert.equal(parseRangeToMs(' 1h '), 60 * 60 * 1000);
});
