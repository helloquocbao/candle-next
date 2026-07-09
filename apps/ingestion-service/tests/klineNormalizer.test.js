'use strict';

const { test } = require('node:test');
const assert = require('node:assert/strict');

const { normalizeRestKline, normalizeWsKline } = require('../src/normalizers/klineNormalizer');

test('normalizeRestKline throws on non-array input', () => {
  assert.throws(() => normalizeRestKline({}, 'BTCUSDT', '1m'), TypeError);
});

test('normalizeRestKline maps Binance REST array to expected shape', () => {
  const raw = [1700000000000, '100.5', '105.2', '99.1', '103.4', '12.3', 1700000059999];
  const result = normalizeRestKline(raw, 'btcusdt', '1m');

  assert.equal(result.symbol, 'BTCUSDT');
  assert.equal(result.interval, '1m');
  assert.equal(result.open, 100.5);
  assert.equal(result.high, 105.2);
  assert.equal(result.low, 99.1);
  assert.equal(result.close, 103.4);
  assert.equal(result.volume, 12.3);
  assert.equal(result.isClosed, true);
  assert.equal(typeof result.openTime, 'string');
  assert.equal(typeof result.closeTime, 'string');
});

test('normalizeWsKline throws on missing k field', () => {
  assert.throws(() => normalizeWsKline({}), TypeError);
  assert.throws(() => normalizeWsKline(null), TypeError);
});

test('normalizeWsKline maps Binance WS payload to expected shape', () => {
  const raw = {
    e: 'kline',
    s: 'btcusdt',
    k: {
      t: 1700000000000,
      T: 1700000059999,
      s: 'BTCUSDT',
      i: '1m',
      o: '100.5',
      h: '105.2',
      l: '99.1',
      c: '103.4',
      v: '12.3',
      x: true,
    },
  };

  const result = normalizeWsKline(raw);

  assert.equal(result.symbol, 'BTCUSDT');
  assert.equal(result.interval, '1m');
  assert.equal(result.open, 100.5);
  assert.equal(result.close, 103.4);
  assert.equal(result.isClosed, true);
});

test('normalizeWsKline preserves isClosed=false for forming candle', () => {
  const raw = {
    k: {
      t: 1700000000000,
      T: 1700000059999,
      s: 'BTCUSDT',
      i: '1m',
      o: '100.5',
      h: '105.2',
      l: '99.1',
      c: '103.4',
      v: '12.3',
      x: false,
    },
  };

  const result = normalizeWsKline(raw);
  assert.equal(result.isClosed, false);
});
