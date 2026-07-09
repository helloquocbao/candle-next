// wsClient.js
// WebSocket client cho api-gateway, theo contract định nghĩa trong
// packages/api-contracts/asyncapi.yaml:
//   -> { "action": "subscribe", "symbol": "BTCUSDT", "interval": "1m" }
//   <- { "type": "kline", "data": {...} }
//   <- { "type": "prediction", "data": {...} }
//   <- { "type": "accuracy_update", "data": {...} }
//
// Tự động reconnect với exponential backoff (giống style
// apps/ingestion-service/src/connectors/binanceWs.js: 1s -> x2 -> tối đa 30s,
// reset backoff khi connect thành công), có heartbeat ping đơn giản.

// api-gateway gắn WebSocketServer tại path "/ws" (xem apps/api-gateway/src/index.js)
const WS_URL = process.env.NEXT_PUBLIC_WS_URL || "ws://localhost:8080/ws";

const INITIAL_BACKOFF_MS = 1000;
const MAX_BACKOFF_MS = 30000;
const HEARTBEAT_INTERVAL_MS = 15000;

export class WsClient {
  constructor(url = WS_URL) {
    this.url = url;
    this.socket = null;
    this.backoffMs = INITIAL_BACKOFF_MS;
    this.reconnectTimer = null;
    this.heartbeatTimer = null;
    this.isClosedByUser = false;
    this.currentSubscription = null; // { symbol, interval }
    this.listeners = {
      kline: new Set(),
      prediction: new Set(),
      accuracy_update: new Set(),
      status: new Set(), // "connecting" | "connected" | "disconnected" | "error"
    };
  }

  connect() {
    this.isClosedByUser = false;
    this._openSocket();
  }

  _openSocket() {
    this._emitStatus("connecting");

    try {
      this.socket = new WebSocket(this.url);
    } catch (err) {
      console.warn("WebSocket construction failed, will retry", err);
      this._scheduleReconnect();
      return;
    }

    this.socket.addEventListener("open", () => {
      this.backoffMs = INITIAL_BACKOFF_MS;
      this._emitStatus("connected");
      this._startHeartbeat();

      // Nếu đã có subscription trước đó (vd sau khi reconnect), gửi lại.
      if (this.currentSubscription) {
        this._sendSubscribe(this.currentSubscription.symbol, this.currentSubscription.interval);
      }
    });

    this.socket.addEventListener("message", (event) => {
      this._handleMessage(event);
    });

    this.socket.addEventListener("close", () => {
      this._stopHeartbeat();
      this._emitStatus("disconnected");
      if (!this.isClosedByUser) {
        this._scheduleReconnect();
      }
    });

    this.socket.addEventListener("error", (err) => {
      console.warn("WebSocket error", err);
      this._emitStatus("error");
      // "close" sẽ được bắn ra ngay sau đó bởi trình duyệt, nơi ta lên lịch reconnect.
    });
  }

  _handleMessage(event) {
    let message;
    try {
      message = JSON.parse(event.data);
    } catch (err) {
      console.warn("Received non-JSON WebSocket message, ignoring", event.data);
      return;
    }

    if (message && message.type === "pong") {
      return; // heartbeat response, không cần dispatch
    }

    const type = message && message.type;
    if (type && this.listeners[type]) {
      this.listeners[type].forEach((callback) => {
        try {
          callback(message.data);
        } catch (err) {
          console.error(`Error in "${type}" listener`, err);
        }
      });
    }
  }

  _scheduleReconnect() {
    if (this.reconnectTimer) return;

    this.reconnectTimer = setTimeout(() => {
      this.reconnectTimer = null;
      this.backoffMs = Math.min(this.backoffMs * 2, MAX_BACKOFF_MS);
      this._openSocket();
    }, this.backoffMs);
  }

  _startHeartbeat() {
    this._stopHeartbeat();
    this.heartbeatTimer = setInterval(() => {
      this._send({ action: "ping" });
    }, HEARTBEAT_INTERVAL_MS);
  }

  _stopHeartbeat() {
    if (this.heartbeatTimer) {
      clearInterval(this.heartbeatTimer);
      this.heartbeatTimer = null;
    }
  }

  _send(payload) {
    if (this.socket && this.socket.readyState === WebSocket.OPEN) {
      this.socket.send(JSON.stringify(payload));
      return true;
    }
    return false;
  }

  _sendSubscribe(symbol, interval) {
    this._send({ action: "subscribe", symbol, interval });
  }

  /**
   * Subscribe vào 1 symbol/interval. Server sẽ bắt đầu đẩy kline/prediction
   * events cho cặp này.
   */
  subscribe(symbol, interval) {
    this.currentSubscription = { symbol, interval };
    this._sendSubscribe(symbol, interval);
  }

  /**
   * Unsubscribe khỏi symbol/interval hiện tại (dùng khi user đổi symbol).
   */
  unsubscribe(symbol, interval) {
    this._send({ action: "unsubscribe", symbol, interval });
    if (
      this.currentSubscription &&
      this.currentSubscription.symbol === symbol &&
      this.currentSubscription.interval === interval
    ) {
      this.currentSubscription = null;
    }
  }

  /**
   * Đăng ký callback theo loại message: "kline" | "prediction" | "accuracy_update" | "status".
   */
  onMessage(type, callback) {
    if (!this.listeners[type]) {
      this.listeners[type] = new Set();
    }
    this.listeners[type].add(callback);
    return () => this.listeners[type].delete(callback);
  }

  _emitStatus(status) {
    this.listeners.status.forEach((callback) => {
      try {
        callback(status);
      } catch (err) {
        console.error("Error in status listener", err);
      }
    });
  }

  close() {
    this.isClosedByUser = true;
    this._stopHeartbeat();
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
    if (this.socket) {
      this.socket.close();
    }
  }
}

// Singleton mặc định dùng chung cho toàn app.
export const wsClient = new WsClient();
