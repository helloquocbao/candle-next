# Chiến lược Doanh thu Bổ sung (Không thu phí người dùng cuối)

Phiên bản: 1.0 · Ngày: 07/07/2026

Tài liệu này bổ sung cho mục "5. Chiến lược tạo doanh thu" trong `project_overview.md` (vốn đã đề cập Ad Networks, Affiliate, Sponsorship). Dưới đây là các mô hình doanh thu **khác**, vẫn giữ nguyên tắc công cụ 100% miễn phí cho end-user cá nhân, dựa trên nghiên cứu các mô hình đang được các nền tảng chart/crypto/fintech áp dụng thực tế.

---

## A. Bán dữ liệu & API cho bên thứ ba (B2B, không phải end-user)

Người dùng cá nhân dùng chart miễn phí, nhưng dữ liệu dự đoán + độ chính xác lịch sử có giá trị với nhà phát triển khác, quỹ nhỏ, hoặc bot trading.

- **API Licensing**: mở API trả phí (theo request hoặc theo tháng) cho lập trình viên/doanh nghiệp muốn tích hợp dữ liệu dự đoán vào sản phẩm của họ — người dùng cuối trên chính website vẫn miễn phí.
- **White-label widget**: cho phép các sàn/dự án nhỏ nhúng chart + dự đoán của bạn vào website họ, thu phí license hoặc revenue-share.
- **Bán dữ liệu lịch sử độ chính xác (accuracy dataset)**: các quỹ định lượng (quant fund) trả phí để backtest hoặc huấn luyện mô hình riêng của họ trên tập dữ liệu dự đoán/kết quả thực tế đã tích luỹ.

## B. Marketplace tín hiệu giao dịch (Signal Marketplace)

Lấy cảm hứng từ mô hình Numerai (giải đấu data science ẩn danh, thưởng bằng crypto cho model chính xác nhất) và SYGNAL (tổng hợp tín hiệu từ nhiều nguồn để bán lại):

- Mở "giải đấu" cho cộng đồng data scientist đóng góp mô hình dự đoán cạnh tranh với thuật toán gốc; thưởng bằng token/crypto cho model tốt nhất, sau đó bán quyền truy cập tín hiệu tổng hợp cho quỹ/trader tổ chức.
- Tạo API "premium signal feed" bán riêng cho tổ chức, trong khi bản hiển thị trên chart công khai vẫn miễn phí nhưng có độ trễ (delay) hoặc độ chi tiết thấp hơn.

## C. Tích hợp Swap/Order Routing (Revenue Share không thu phí trực tiếp)

Theo mô hình các ví crypto hiện đại (vd: Flashift): nhúng một widget swap non-custodial (DEX aggregator) ngay cạnh chart, cho phép người dùng chuyển đổi coin dựa trên dự đoán. Người dùng không bị tính thêm phí ngoài phí thị trường; nền tảng nhận hoa hồng nhỏ từ nhà cung cấp thanh khoản (liquidity provider) trên mỗi giao dịch được route qua.

- Khác với affiliate đăng ký sàn (one-time/ref %), đây là doanh thu theo từng giao dịch swap, không cần người dùng rời khỏi trang.

## D. Payment for Order Flow kiểu Crypto (Rebate liên tục)

Mở rộng mô hình affiliate hiện tại: thay vì chỉ nhận % hoa hồng khi user đăng ký, đàm phán **rebate trên mỗi lệnh giao dịch** được thực hiện qua API của sàn khi user click "giao dịch theo dự đoán". Đây gần với PFOF (payment for order flow) mà các nền tảng trading miễn phí (Robinhood-style) áp dụng — tăng dòng tiền định kỳ thay vì chỉ một lần.

## E. Phí niêm yết / làm nổi bật (Listing & Placement Fee)

- Các dự án token mới trả phí để coin của họ được thêm vào danh sách cặp giao dịch hỗ trợ trên chart (tương tự listing fee của sàn).
- Bán vị trí "Trending/Hot pairs" trên UI cho các dự án muốn tăng độ nhận diện — tách biệt với mục C (sponsorship logo) đã có trong overview vì đây là fee định kỳ theo vị trí hiển thị, không phải hợp đồng tài trợ dài hạn.

## F. Kho chỉ báo & chiến lược do cộng đồng đóng góp (Strategy/Indicator Store)

Theo mô hình TrendSpider: cho phép người dùng nâng cao tạo chỉ báo/chiến lược tùy chỉnh dựa trên nền tảng dự đoán, đăng bán trên "store" nội bộ. Nền tảng thu % hoa hồng trên mỗi giao dịch bán chỉ báo — bản thân chart gốc vẫn miễn phí, chỉ tính năng mở rộng do bên thứ ba tạo ra mới có phí.

## G. Grant & Tài trợ hệ sinh thái (Ecosystem Grants)

- Nhiều blockchain foundation (Binance Labs, Solana Foundation, v.v.) cấp grant không hoàn lại cho công cụ open-source/miễn phí phục vụ cộng đồng trader. Nộp hồ sơ xin grant định kỳ là nguồn thu không ảnh hưởng đến trải nghiệm miễn phí.
- Tham gia hackathon crypto để nhận giải thưởng, đồng thời tăng độ nhận diện dự án.

## H. Dữ liệu tổng hợp ẩn danh (Aggregated Insights-as-a-Service)

Tổng hợp hành vi sử dụng ẩn danh (coin nào được xem nhiều nhất, khung giờ traffic cao, độ chính xác theo từng cặp coin) thành báo cáo thị trường bán cho các bên nghiên cứu/truyền thông crypto — không bán dữ liệu cá nhân, chỉ bán insight tổng hợp.

---

## Bảng so sánh & mức độ ưu tiên

| Chiến lược | Yêu cầu kỹ thuật thêm | Thời gian có doanh thu | Rủi ro/hạn chế |
|---|---|---|---|
| A. API/Data Licensing | Trung bình (cần API auth, billing) | Trung hạn | Cần lượng dữ liệu đủ lớn để hấp dẫn khách B2B |
| B. Signal Marketplace | Cao (giải đấu, hệ thống chấm điểm) | Dài hạn | Cần cộng đồng data scientist, phức tạp vận hành |
| C. Swap widget revenue share | Thấp-Trung bình (tích hợp SDK có sẵn) | Ngắn hạn | Phụ thuộc đối tác DEX/aggregator, cần tuân thủ pháp lý theo khu vực |
| D. Rebate liên tục (PFOF-style) | Thấp (mở rộng affiliate hiện có) | Ngắn hạn | Cần đàm phán riêng với từng sàn |
| E. Listing/Placement fee | Thấp | Ngắn-Trung hạn | Cần traffic đủ lớn để có giá trị bán |
| F. Indicator/Strategy Store | Cao (payment system, review nội dung) | Dài hạn | Cần user base kỹ thuật cao mới có người bán |
| G. Grants | Thấp (chỉ cần viết hồ sơ) | Không chắc chắn/thời điểm | Cạnh tranh cao, không lặp lại đều đặn |
| H. Aggregated Insights | Trung bình (ẩn danh hoá, phân tích) | Trung-Dài hạn | Cần khối lượng người dùng đủ lớn để dữ liệu có giá trị |

## Đề xuất triển khai theo giai đoạn

1. **Ngắn hạn (song song MVP)**: D (mở rộng rebate affiliate) và C (swap widget) — tận dụng hạ tầng sẵn có, triển khai nhanh, không cần thêm nhiều engineering.
2. **Trung hạn (sau khi có traffic ổn định)**: A (API licensing cơ bản) và E (listing/placement fee) — cần dữ liệu/traffic đạt ngưỡng đủ hấp dẫn đối tác.
3. **Dài hạn (khi có cộng đồng lớn)**: B (signal marketplace) và F (indicator store) — cần effort vận hành cộng đồng đáng kể.
4. **Cơ hội thời điểm**: G (grants) nên nộp hồ sơ sớm và song song, không phụ thuộc tiến độ sản phẩm.

---

## Nguồn tham khảo

- [How To Monetize A Crypto Wallet (2026)](https://flashift.app/blog/how-to-monetize-a-crypto-wallet/)
- [Monetize a Crypto Exchange: Beyond Trading Fees](https://www.bitdeal.net/how-to-monetize-a-crypto-exchange-beyond-trading-fees)
- [Crypto monetization or revenue streams — FasterCapital](https://fastercapital.com/content/Crypto-monetization-or-revenue-streams--Entrepreneur-s-Guide-to-Crypto-Monetization--Revenue-Strategies-Unleashed.html)
- [Best Free Stock Charts: Platforms Compared (2026)](https://www.newtrading.io/free-stock-charts/)
- [How to Monetize a Prediction Market Platform](https://ericaai.tech.blog/2026/04/09/how-to-monetize-a-prediction-market-platform/)
- [SYGNAL — Driven Trading](https://sygnal.ai/)
