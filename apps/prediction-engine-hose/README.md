# prediction-engine-hose

Core dự đoán **vùng giá tương lai** cho cổ phiếu **HOSE** — service ĐỘC LẬP,
tách hoàn toàn khỏi `prediction-engine` (crypto). Sửa/khởi động lại service
này không ảnh hưởng core crypto.

## Mục tiêu
Sinh vùng giá dự đoán N phiên tới (mặc định 5) dưới dạng hộp trên/dưới bất
đối xứng (giống forecast zone của app crypto), **bị chặn trong phễu trần/sàn
±7%/phiên của HOSE**, đặt trên các phiên giao dịch kế tiếp (bỏ cuối tuần/lễ).

## Nguồn dữ liệu
VNDIRECT dchart (UDF, công khai, không cần key) — daily OHLCV. TCBS đã đổi
API (404) nên không dùng. Dữ liệu chỉ để hiển thị tham khảo; đọc ToS trước
khi thương mại hoá.

## Trạng thái
- **Phase 1 (xong):** module đặc thù HOSE, tự chứa, có test.
  - `src/price_limit.py` — phễu trần/sàn ±7% lũy tiến.
  - `src/calendar_hose.py` — lịch phiên (ngày giao dịch, N phiên kế tiếp).
  - `src/connectors/vndirect.py` — lấy + chuẩn hoá OHLCV daily.
- **Phase 2 (kế tiếp):** builder vùng giá (model kỳ vọng + band ATR ∩ phễu).
- **Phase 3:** wiring hạ tầng (DB/Redis, ghi predictions theo `market=hose`).
- **Phase 4:** frontend toggle Crypto / CK VN.

## Chạy test
```bash
cd apps/prediction-engine-hose && python3 -m pytest
```
