'use strict';

const { test } = require('node:test');
const assert = require('node:assert/strict');

const {
  splitSymbol,
  parseInterval,
  toOkxInstId,
  toOkxBar,
  toBybitSymbol,
  toBybitInterval,
} = require('../src/exchanges/symbolFormat');

test('splitSymbol tach dung base/quote cho quote pho bien', () => {
  assert.deepEqual(splitSymbol('BTCUSDT'), { base: 'BTC', quote: 'USDT' });
  assert.deepEqual(splitSymbol('ETHUSDC'), { base: 'ETH', quote: 'USDC' });
  assert.deepEqual(splitSymbol('SOLBTC'), { base: 'SOL', quote: 'BTC' });
});

test('splitSymbol uu tien quote DAI hon (USDT khong bi cat thanh USD)', () => {
  assert.deepEqual(splitSymbol('BTCUSDT'), { base: 'BTC', quote: 'USDT' });
});

test('splitSymbol tra ve null khi khong nhan dien duoc quote', () => {
  assert.equal(splitSymbol('FOOBAR'), null);
});

test('parseInterval phan biet hoa/thuong m (phut) va M (thang)', () => {
  assert.deepEqual(parseInterval('1m'), { amount: 1, unit: 'm' });
  assert.deepEqual(parseInterval('1M'), { amount: 1, unit: 'M' });
  assert.deepEqual(parseInterval('4h'), { amount: 4, unit: 'h' });
});

test('parseInterval bao loi voi interval khong hop le', () => {
  assert.throws(() => parseInterval('abc'));
  assert.throws(() => parseInterval('1x'));
});

test('toOkxInstId chuyen BTCUSDT -> BTC-USDT', () => {
  assert.equal(toOkxInstId('BTCUSDT'), 'BTC-USDT');
  assert.equal(toOkxInstId('ethusdt'), 'ETH-USDT');
});

test('toOkxBar giu phut thuong, viet hoa gio/ngay/tuan/thang', () => {
  assert.equal(toOkxBar('1m'), '1m');
  assert.equal(toOkxBar('15m'), '15m');
  assert.equal(toOkxBar('1h'), '1H');
  assert.equal(toOkxBar('4h'), '4H');
  assert.equal(toOkxBar('1d'), '1D');
  assert.equal(toOkxBar('1w'), '1W');
  assert.equal(toOkxBar('1M'), '1M');
});

test('toBybitSymbol giu nguyen dang BTCUSDT', () => {
  assert.equal(toBybitSymbol('btcusdt'), 'BTCUSDT');
});

test('toBybitInterval quy phut/gio ve so phut, ngay/tuan/thang la ky tu', () => {
  assert.equal(toBybitInterval('1m'), '1');
  assert.equal(toBybitInterval('5m'), '5');
  assert.equal(toBybitInterval('1h'), '60');
  assert.equal(toBybitInterval('4h'), '240');
  assert.equal(toBybitInterval('1d'), 'D');
  assert.equal(toBybitInterval('1w'), 'W');
  assert.equal(toBybitInterval('1M'), 'M');
});
