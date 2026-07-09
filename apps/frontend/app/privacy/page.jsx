import LegalShell from "../../components/LegalShell";

export const metadata = { title: "Chính sách bảo mật — CryptoPredict" };

export default function PrivacyPage() {
  return (
    <LegalShell title="Chính sách bảo mật" updated="Cập nhật lần cuối: 2026">
      <p>Chính sách này mô tả cách CryptoPredict xử lý thông tin khi bạn truy cập.</p>
      <h2>1. Dữ liệu chúng tôi lưu</h2>
      <p>
        Trang <strong>không yêu cầu đăng ký tài khoản</strong> và không thu thập thông tin định
        danh cá nhân. Tuỳ chọn hiển thị (symbol, khung thời gian, thị trường, theme) được lưu
        <em> cục bộ trên trình duyệt</em> qua localStorage, không gửi về máy chủ.
      </p>
      <h2>2. Cookie và quảng cáo</h2>
      <p>
        Trang có thể hiển thị quảng cáo từ đối tác thứ ba, có thể dùng cookie để phục vụ quảng
        cáo phù hợp. Bạn có thể tắt cookie trong trình duyệt mà không ảnh hưởng chức năng biểu đồ.
      </p>
      <h2>3. Dữ liệu phân tích</h2>
      <p>Có thể dùng công cụ phân tích lưu lượng ẩn danh, dạng tổng hợp, không định danh cá nhân.</p>
      <h2>4. Liên kết bên ngoài</h2>
      <p>Trang có thể chứa liên kết tới sàn/website bên thứ ba; chúng tôi không chịu trách nhiệm về nội dung/chính sách của họ.</p>
      <p className="legal-note">
        Xem thêm <a href="/terms">Điều khoản sử dụng</a>.
      </p>
    </LegalShell>
  );
}
