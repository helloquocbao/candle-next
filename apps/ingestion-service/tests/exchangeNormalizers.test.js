'use strict';

const { test } = require('node:test');
const assert = require('node:assert/strict');

const { normalizeOkxKline } = require('../src/normalizers/okxNormalizer');
const {
  normalizeBybitRestKline,
  normalizeBybitWsKline,
} = require('../src/normalizers/bybitNormalizer');

// ------------------------------------------------------------------- OKX --

test('normalizeOkxKline map mang OKX ve shape chung, confirm=1 -> isClosed', () => {
  // [ ts, o, h, l, c, vol, volCcy, volCcyQuote, confirm ]
  const raw = ['1700000000000', '100.5', '105.2', '99.1', '103.4', '12.3', '0', '0', '1'];
  const result = normalizeOkxKline(raw, 'BTCUSDT', '1m');

  assert.equal(result.symbol, 'BTCUSDT');
  assert.equal(result.interval, '1m');
  assert.equal(result.open, 100.5);
  assert.equal(result.high, 105.2);
  assert.equal(result.low, 99.1);
  assert.equal(result.close, 103.4);
  assert.equal(result.volume, 12.3);
  assert.equal(result.isClosed, true);
  assert.equal(result.openTime, new Date(1700000000000).toISOString());
  // closeTime = openTime + 60s - 1ms
  assert.equal(result.closeTime, new Date(1700000000000 + 60000 - 1).toISOString());
});

test('normalizeOkxKline confirm=0 -> nen dang hinh thanh (isClosed=false)', () => {
  const raw = ['1700000000000', '100', '101', '99', '100.5', '5', '0', '0', '0'];
  const result = normalizeOkxKline(raw, 'ETHUSDT', '1m');
  assert.equal(result.isClosed, false);
});

test('normalizeOkxKline nem loi khi input khong phai mang', () => {
  assert.throws(() => normalizeOkxKline({}, 'BTCUSDT', '1m'), TypeError);
});

// ----------------------------------------------------------------- Bybit --

test('normalizeBybitRestKline map mang REST ve shape chung (isClosed=true)', () => {
  // [ start, open, high, low, close, volume, turnover ]
  const raw = ['1700000000000', '100.5', '105.2', '99.1', '103.4', '12.3', '999'];
  const result = normalizeBybitRestKline(raw, 'BTCUSDT', '1m');

  assert.equal(result.symbol, 'BTCUSDT');
  assert.equal(result.open, 100.5);
  assert.equal(result.close, 103.4);
  assert.equal(result.volume, 12.3);
  assert.equal(result.isClosed, true);
});

test('normalizeBybitWsKline map object WS, confirm=true -> isClosed', () => {
  const raw = {
    start: 1700000000000,
    end: 1700000059999,
    interval: '1',
    open: '100.5',
    high: '105.2',
    low: '99.1',
    close: '103.4',
    volume: '12.3',
    confirm: true,
    timestamp: 1700000059000,
  };
  const result = normalizeBybitWsKline(raw, 'BTCUSDT', '1m');

  assert.equal(result.symbol, 'BTCUSDT');
  assert.equal(result.interval, '1m');
  assert.equal(result.open, 100.5);
  assert.equal(result.close, 103.4);
  assert.equal(result.isClosed, true);
  assert.equal(result.closeTime, new Date(1700000059999).toISOString());
});

test('normalizeBybitWsKline confirm=false -> nen dang hinh thanh', () => {
  const raw = {
    start: 1700000000000,
    end: 1700000059999,
    open: '100',
    high: '101',
    low: '99',
    close: '100.5',
    volume: '5',
    confirm: false,
  };
  const result = normalizeBybitWsKline(raw, 'BTCUSDT', '1m');
  assert.equal(result.isClosed, false);
});

test('normalizeBybitWsKline nem loi khi input la mang/khong phai object', () => {
  assert.throws(() => normalizeBybitWsKline([], 'BTCUSDT', '1m'), TypeError);
  assert.throws(() => normalizeBybitWsKline(null, 'BTCUSDT', '1m'), TypeError);
});
