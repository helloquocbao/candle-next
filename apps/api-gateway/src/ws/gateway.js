// WebSocket gateway — xử lý subscribe realtime cho kline/prediction/accuracy_update
//
// Cách tiếp cận (đơn giản, có comment giải thích):
// Mỗi WebSocket connection từ client sẽ tạo MỘT ioredis client riêng dùng để
// subscribe các channel Redis pub/sub tương ứng. Lý do chọn "1 client riêng
// mỗi connection" thay vì dùng chung 1 client global với psubscribe pattern:
//   - Đơn giản để cleanup: khi client disconnect chỉ cần quit() client đó.
//   - Tránh phải tự quản lý map "channel -> danh sách client nào đang nghe"
//     để forward message cho đúng người (dùng chung 1 subscriber sẽ nhận
//     event của TẤT CẢ client rồi phải tự route lại theo ws connection).
//   - Đánh đổi: tốn nhiều kết nối Redis hơn nếu có rất nhiều client đồng thời.
//     Với quy mô hiện tại (crypto predictor chart, vài chục-vài trăm client)
//     là chấp nhận được. Có thể tối ưu sau bằng pattern subscribe dùng chung.
const Redis = require('ioredis');
const env = require('../config/env');

function buildChannels(symbol, interval) {
  return {
    kline: `klines:${symbol}:${interval}`,
    prediction: `predictions:${symbol}:${interval}`,
    accuracy: `accuracy:${symbol}:${interval}`,
  };
}

function attachWebSocketGateway(wss) {
  wss.on('connection', (ws) => {
    // Mỗi connection có 1 subscriber riêng + biết mình đang subscribe channel nào
    let subscriber = null;
    let currentChannels = null;

    function cleanup() {
      if (subscriber) {
        subscriber.removeAllListeners('message');
        subscriber.quit().catch(() => {
          // ignore lỗi khi đóng kết nối redis lúc cleanup
        });
        subscriber = null;
      }
      currentChannels = null;
    }

    ws.on('message', async (raw) => {
      let payload;
      try {
        payload = JSON.parse(raw.toString());
      } catch (err) {
        ws.send(JSON.stringify({ type: 'error', data: { message: 'Message không phải JSON hợp lệ' } }));
        return;
      }

      const { action, symbol, interval } = payload || {};

      if (action === 'ping') {
        ws.send(JSON.stringify({ type: 'pong' }));
        return;
      }

      if (action === 'unsubscribe') {
        cleanup();
        ws.send(JSON.stringify({ type: 'unsubscribed', data: { symbol, interval } }));
        return;
      }

      if (action !== 'subscribe') {
        ws.send(JSON.stringify({ type: 'error', data: { message: `Action không hỗ trợ: ${action}` } }));
        return;
      }

      if (!symbol || !interval) {
        ws.send(JSON.stringify({ type: 'error', data: { message: 'Thiếu symbol hoặc interval' } }));
        return;
      }

      // Nếu client subscribe lại (đổi symbol/interval) thì dọn subscription cũ trước
      cleanup();

      currentChannels = buildChannels(symbol, interval);
      subscriber = new Redis(env.REDIS_URL);

      subscriber.on('error', (err) => {
        // eslint-disable-next-line no-console
        console.error('[ws/gateway] Lỗi redis subscriber:', err);
      });

      try {
        await subscriber.subscribe(
          currentChannels.kline,
          currentChannels.prediction,
          currentChannels.accuracy
        );
      } catch (err) {
        // eslint-disable-next-line no-console
        console.error('[ws/gateway] Lỗi subscribe channel:', err);
        ws.send(JSON.stringify({ type: 'error', data: { message: 'Không thể subscribe kênh dữ liệu' } }));
        return;
      }

      subscriber.on('message', (channel, message) => {
        if (ws.readyState !== ws.OPEN) return;

        // Producer (ingestion-service/prediction-engine) da publish DUNG
        // envelope wire-format theo asyncapi.yaml ngay tren Redis:
        //   { "type": "kline", "data": {...} }
        //   { "type": "prediction", "data": {...} }
        //   { "type": "accuracy_update", "data": {...} }
        // => forward nguyen van message, KHONG boc them 1 lop {type,data}
        // nua (bug da tung xay ra: client nhan duoc {type,data:{type,data:{...}}}
        // vi gateway tu suy ra type tu ten channel roi wrap lai message da
        // wrap san cua producer).
        ws.send(message);
      });
    });

    ws.on('close', () => {
      cleanup();
    });

    ws.on('error', () => {
      cleanup();
    });
  });
}

module.exports = attachWebSocketGateway;
