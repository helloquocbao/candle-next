import LegalShell from "../../components/LegalShell";

export const metadata = { title: "Điều khoản sử dụng — CryptoPredict" };

export default function TermsPage() {
  return (
    <LegalShell title="Điều khoản sử dụng" updated="Cập nhật lần cuối: 2026">
      <p>
        Bằng việc truy cập và sử dụng CryptoPredict (&quot;Trang&quot;), bạn đồng ý với các điều
        khoản dưới đây. Nếu không đồng ý, vui lòng ngừng sử dụng Trang.
      </p>
      <h2>1. Bản chất dịch vụ</h2>
      <p>
        Trang cung cấp biểu đồ giá crypto và cổ phiếu HOSE theo thời gian thực và
        <strong> vùng nến dự đoán do thuật toán tự động tạo ra</strong>. Đây là công cụ trực
        quan hoá và thử nghiệm kỹ thuật, phục vụ tham khảo và giáo dục.
      </p>
      <h2>2. Miễn trừ trách nhiệm đầu tư</h2>
      <p>
        <strong>
          Nội dung trên Trang KHÔNG phải lời khuyên đầu tư, tư vấn tài chính, hay khuyến nghị
          mua/bán bất kỳ tài sản nào.
        </strong>{" "}
        Các dự đoán được sinh tự động và có thể sai. Giao dịch tài sản số/chứng khoán có rủi ro
        cao và có thể dẫn tới mất toàn bộ vốn. Mọi quyết định là của riêng bạn.
      </p>
      <h2>3. Nguồn dữ liệu</h2>
      <p>
        Dữ liệu thị trường lấy từ API công khai của Binance, OKX, Bybit (crypto) và VNDIRECT
        (HOSE), chỉ nhằm mục đích hiển thị. Chúng tôi không đảm bảo dữ liệu luôn chính xác/đầy
        đủ. Thương hiệu thuộc về chủ sở hữu tương ứng.
      </p>
      <h2>4. Duy trì hoạt động</h2>
      <p>
        Trang được duy trì phi lợi nhuận qua quảng cáo, liên kết giới thiệu và/hoặc đóng góp tự
        nguyện — không đổi lại lợi ích tài chính hay dịch vụ đầu tư nào.
      </p>
      <p className="legal-note">
        Xem thêm <a href="/privacy">Chính sách bảo mật</a>.
      </p>
    </LegalShell>
  );
}
