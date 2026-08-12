# prediction-engine-hose

Core dự đoán **vùng giá tương lai** cho cổ phiếu **HOSE** — service ĐỘC LẬP,
tách hoàn toàn khỏi `prediction-engine` (crypto). Sửa/khởi động lại service
này không ảnh hưởng core crypto.

## Mục tiêu
Sinh vùng giá dự đoán N phiên tới (mặc định 5) dưới dạng hộp trên/dưới bất
đối xứng (giống forecast zone của app crypto), đặt trên các phiên giao dịch
kế tiếp (bỏ cuối tuần/lễ). Vùng giá **chạy tự do theo model** (drift EMA +
ATR nở dần theo bước) — KHÔNG bị chặn bởi biên độ giao dịch ±7%/phiên của
HOSE, để phản ánh đúng "vùng giá có thể chạy tới trong tương lai" theo dữ
liệu, thay vì biên độ giao dịch lý thuyết của sàn.

## Nguồn dữ liệu
`vnstock` (qua `src/connectors/vndirect.py::fetch_daily_ohlcv`) — daily
OHLCV. Dữ liệu chỉ để hiển thị tham khảo; đọc ToS trước khi thương mại hoá.

## Trạng thái
- **Phase 1 (xong):** module đặc thù HOSE, tự chứa, có test.
  - `src/price_limit.py` — helper tính phễu trần/sàn ±7% (KHÔNG còn được gọi
    tự động trong pipeline chính từ khi bỏ ràng buộc phễu; giữ lại cho ai
    cần dùng lại/so sánh).
  - `src/calendar_hose.py` — lịch phiên (ngày giao dịch, N phiên kế tiếp).
  - `src/connectors/vndirect.py` — lấy + chuẩn hoá OHLCV daily.
- **Phase 2 (xong):** `src/forecast_zone.py` — builder vùng giá (drift EMA +
  band ATR nở dần theo bước, KHÔNG kẹp phễu).
- **Phase 3 (xong):** wiring hạ tầng — `src/db.py` ghi `klines`/`predictions`
  với `market='hose'`, `src/main.py` chạy vòng lặp EOD (`REFRESH_INTERVAL_SEC`)
  gọi VNDIRECT → upsert klines → dựng vùng giá → ghi predictions. Chưa có
  Redis pub/sub/WebSocket cho HOSE (khác crypto) — frontend đọc qua REST
  poll (`GET /api/v1/predictions/latest?symbol=...`), phù hợp vì dữ liệu chỉ
  cập nhật EOD (không cần đẩy real-time).
- **Phase 4 (xong, phía frontend):** `apps/frontend/components/ChartApp.jsx`
  đã có toggle Crypto / "CK VN" (market=hose), tự giới hạn khung thời gian
  chỉ `1d` khi ở chế độ HOSE.
- **Ensemble AI (DeepSeek, mới):** xem mục riêng bên dưới.

## Ensemble AI (DeepSeek)

`src/ai_advisor.py` — tín hiệu BỔ SUNG (ensemble) từ DeepSeek Chat API kết
hợp với vùng giá định lượng (`forecast_zone.py`), KHÔNG thay thế. Chỉ áp
dụng cho phiên **t+1** (`zone["predictions"][0]`) — các phiên t+2..t+N vẫn
thuần định lượng như trước.

Cách hoạt động: mỗi chu kỳ EOD (mặc định 1 lần/giờ, `REFRESH_INTERVAL_SEC`),
với mỗi mã, gọi DeepSeek với giá đóng cửa gần đây + dự đoán của
`forecast_zone.py`, nhận về `{direction, predicted_change_pct, confidence,
reasoning}`, rồi blend theo trọng số `DEEPSEEK_WEIGHT` (mặc định `0.35`).
`predicted_change_pct` chỉ bị chặn an toàn rộng (`SAFETY_CLAMP_PCT`, mặc
định ±30%, không liên quan biên độ HOSE) để loại giá trị hallucination phi
lý — **kết quả blend KHÔNG còn bị kẹp vào phễu ±7%** như trước. Không cần
throttle riêng như bên `prediction-engine` (crypto, 1 nến/phút) vì tần suất
gọi ở đây đã thấp sẵn (1 lần/mã/chu kỳ EOD).

**Mặc định TẮT** (`DEEPSEEK_ENABLED=false`, dùng chung biến môi trường với
`prediction-engine`, xem `.env.example`). Mọi lỗi mạng/timeout/JSON không
parse được đều fallback về đúng vùng giá định lượng gốc — không chặn chu kỳ
EOD vì 1 mã lỗi AI.

**Audit trail**: mỗi tín hiệu AI được blend ghi vào bảng `ai_signals`
(`infra/db/migrations/006_ai_signals.sql`, `market='hose'`), và
`model_version` của phiên t+1 được gắn thêm hậu tố `+deepseek` (vd
`hose-freerange-v1+deepseek`) để sau này lọc `accuracy_log` so sánh khách
quan hiệu quả thực tế trước khi tăng `DEEPSEEK_WEIGHT`.

## Chạy test
```bash
cd apps/prediction-engine-hose && python3 -m pytest
```
