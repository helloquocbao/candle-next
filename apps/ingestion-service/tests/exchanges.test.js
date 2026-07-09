'use strict';

const { test } = require('node:test');
const assert = require('node:assert/strict');

const { parseSymbolPairsEnv } = require('../src/trackedPairs');
const { getExchangeAdapter, SUPPORTED_EXCHANGES } = require('../src/exchanges');

test('parseSymbolPairsEnv van tuong thich cap 2 segment (khong sinh key exchange)', () => {
  const pairs = parseSymbolPairsEnv('BTCUSDT:1m,ETHUSDT:5m');
  assert.deepEqual(pairs, [
    { symbol: 'BTCUSDT', interval: '1m' },
    { symbol: 'ETHUSDT', interval: '5m' },
  ]);
});

test('parseSymbolPairsEnv doc segment thu 3 lam exchange (chuyen chu thuong)', () => {
  const pairs = parseSymbolPairsEnv('BTCUSDT:1m:OKX, ETHUSDT:5m:bybit ,SOLUSDT:1m');
  assert.deepEqual(pairs, [
    { symbol: 'BTCUSDT', interval: '1m', exchange: 'okx' },
    { symbol: 'ETHUSDT', interval: '5m', exchange: 'bybit' },
    { symbol: 'SOLUSDT', interval: '1m' },
  ]);
});

test('getExchangeAdapter tra ve adapter dung ten (khong phan biet hoa/thuong)', () => {
  assert.equal(getExchangeAdapter('okx').name, 'okx');
  assert.equal(getExchangeAdapter('BYBIT').name, 'bybit');
  assert.equal(getExchangeAdapter('binance').name, 'binance');
});

test('getExchangeAdapter fallback ve binance khi ten san khong ho tro', () => {
  assert.equal(getExchangeAdapter('kraken').name, 'binance');
  assert.equal(getExchangeAdapter(undefined).name, 'binance');
});

test('moi adapter phoi bay interface chung fetchHistory + connectStream', () => {
  for (const name of SUPPORTED_EXCHANGES) {
    const adapter = getExchangeAdapter(name);
    assert.equal(typeof adapter.fetchHistory, 'function');
    assert.equal(typeof adapter.connectStream, 'function');
  }
});
