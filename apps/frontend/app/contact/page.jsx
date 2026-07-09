import LegalShell from "../../components/LegalShell";

export const metadata = { title: "Liên hệ — CryptoPredict" };

export default function ContactPage() {
  return (
    <LegalShell title="Liên hệ">
      <p>Nếu bạn có câu hỏi, góp ý hoặc phản hồi về CryptoPredict, hãy liên hệ qua:</p>
      {/* TODO: thay bằng email/kênh liên hệ thật trước khi công khai. */}
      <ul>
        <li>Email: <a href="mailto:contact@example.com">contact@example.com</a></li>
      </ul>
      <p>Chúng tôi hoan nghênh mọi phản hồi giúp cải thiện chất lượng dự đoán và trải nghiệm.</p>
      <p className="legal-note">
        Lưu ý: chúng tôi không cung cấp tư vấn đầu tư cá nhân. Xem{" "}
        <a href="/terms">Điều khoản sử dụng</a>.
      </p>
    </LegalShell>
  );
}
