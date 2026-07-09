// Footer dùng chung cho các trang tĩnh (landing + pháp lý).
export default function SiteFooter({ full = true }) {
  return (
    <footer className="site-footer">
      <nav className="footer-links" aria-label="Liên kết chân trang">
        <a href="/about">Giới thiệu</a>
        <a href="/terms">Điều khoản sử dụng</a>
        <a href="/privacy">Chính sách bảo mật</a>
        <a href="/contact">Liên hệ</a>
      </nav>
      {full && (
        <p className="footer-disclaimer">
          <strong>Miễn trừ trách nhiệm:</strong> Các vùng nến dự đoán do thuật toán tự
          động tạo ra, chỉ mang tính tham khảo và thử nghiệm, KHÔNG phải lời khuyên đầu
          tư hay khuyến nghị mua/bán. Giao dịch tài sản số/chứng khoán có rủi ro cao; bạn
          tự chịu trách nhiệm cho quyết định của mình.
        </p>
      )}
      <p className="footer-copyright">© 2026 CryptoPredict</p>
    </footer>
  );
}
