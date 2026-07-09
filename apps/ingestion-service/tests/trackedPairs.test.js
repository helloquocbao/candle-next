'use strict';

const { test } = require('node:test');
const assert = require('node:assert/strict');

const { resolveTrackedPairs, parseSymbolPairsEnv } = require('../src/trackedPairs');

test('parseSymbolPairsEnv parses "SYMBOL:interval" list phan cach boi dau phay', () => {
  const pairs = parseSymbolPairsEnv('BTCUSDT:1m, ethusdt:5m ,SOLUSDT:1m');
  assert.deepEqual(pairs, [
    { symbol: 'BTCUSDT', interval: '1m' },
    { symbol: 'ETHUSDT', interval: '5m' },
    { symbol: 'SOLUSDT', interval: '1m' },
  ]);
});

test('parseSymbolPairsEnv bao loi neu thieu interval', () => {
  assert.throws(() => parseSymbolPairsEnv('BTCUSDT'));
});

test('resolveTrackedPairs uu tien SYMBOL_PAIRS env', async () => {
  const pairs = await resolveTrackedPairs({
    env: { SYMBOL_PAIRS: 'BTCUSDT:1m,ETHUSDT:1m' },
    getTrackedPairsFromDb: async () => {
      throw new Error('khong duoc goi khi da co SYMBOL_PAIRS');
    },
  });
  assert.deepEqual(pairs, [
    { symbol: 'BTCUSDT', interval: '1m' },
    { symbol: 'ETHUSDT', interval: '1m' },
  ]);
});

test('resolveTrackedPairs doc tu DB khi khong co SYMBOL_PAIRS', async () => {
  const pairs = await resolveTrackedPairs({
    env: {},
    getTrackedPairsFromDb: async () => [
      { symbol: 'BTCUSDT', interval: '1m' },
      { symbol: 'SOLUSDT', interval: '1m' },
    ],
  });
  assert.deepEqual(pairs, [
    { symbol: 'BTCUSDT', interval: '1m' },
    { symbol: 'SOLUSDT', interval: '1m' },
  ]);
});

test('resolveTrackedPairs fallback ve SYMBOL/INTERVAL sau khi het luot retry', async () => {
  let callCount = 0;
  const pairs = await resolveTrackedPairs({
    env: { SYMBOL: 'ETHUSDT', INTERVAL: '5m' },
    maxAttempts: 3,
    retryDelayMs: 0,
    getTrackedPairsFromDb: async () => {
      callCount += 1;
      throw new Error('DB down');
    },
  });
  assert.deepEqual(pairs, [{ symbol: 'ETHUSDT', interval: '5m' }]);
  assert.equal(callCount, 3);
});

test('resolveTrackedPairs thu lai va thanh cong sau vai lan DB chua san sang', async () => {
  let callCount = 0;
  const pairs = await resolveTrackedPairs({
    env: {},
    maxAttempts: 5,
    retryDelayMs: 0,
    getTrackedPairsFromDb: async () => {
      callCount += 1;
      if (callCount < 3) throw new Error('the database system is starting up');
      return [{ symbol: 'BTCUSDT', interval: '1m' }];
    },
  });
  assert.deepEqual(pairs, [{ symbol: 'BTCUSDT', interval: '1m' }]);
  assert.equal(callCount, 3);
});

test('resolveTrackedPairs fallback mac dinh BTCUSDT/1m khi khong co gi ca', async () => {
  const pairs = await resolveTrackedPairs({ env: {} });
  assert.deepEqual(pairs, [{ symbol: 'BTCUSDT', interval: '1m' }]);
});
