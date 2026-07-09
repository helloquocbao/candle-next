import LegalShell from "../../components/LegalShell";

export const metadata = { title: "Giới thiệu — CryptoPredict" };

export default function AboutPage() {
  return (
    <LegalShell title="Giới thiệu">
      <p>
        CryptoPredict là công cụ trực quan hoá biểu đồ nến crypto &amp; cổ phiếu HOSE theo thời
        gian thực, kèm <strong>vùng nến dự đoán</strong> sinh tự động bằng thuật toán thống kê và
        máy học. Mục tiêu: cách nhìn trực quan về xu hướng thị trường cho mục đích tham khảo và
        học tập.
      </p>
      <h2>Cách hoạt động</h2>
      <ul>
        <li>Thu thập dữ liệu nến từ API công khai (Binance/OKX/Bybit cho crypto, VNDIRECT cho HOSE).</li>
        <li>Mô hình dự đoán chạy vòng lặp tự học, liên tục đánh giá độ chính xác.</li>
        <li>Kết quả hiển thị dưới dạng vùng giá dự đoán nhiều bước, kèm độ chính xác gần đây.</li>
      </ul>
      <h2>Lưu ý quan trọng</h2>
      <p>
        Đây là dự án kỹ thuật thử nghiệm. Mọi dự đoán chỉ để tham khảo,{" "}
        <strong>không phải lời khuyên đầu tư</strong>. Xem{" "}
        <a href="/terms">Điều khoản sử dụng</a>.
      </p>
    </LegalShell>
  );
}
