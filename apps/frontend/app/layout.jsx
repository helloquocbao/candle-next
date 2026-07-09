import "./globals.css";
import ThemeInit from "../components/ThemeInit";

export const metadata = {
  title: "CryptoPredict — Biểu đồ crypto & chứng khoán real-time, dự đoán AI",
  description:
    "Biểu đồ nến crypto & HOSE real-time kèm vùng dự đoán tương lai bằng thuật toán tự học. Miễn phí, không cần đăng ký.",
};

export default function RootLayout({ children }) {
  return (
    <html lang="vi">
      <body>
        {/* Khôi phục theme sáng/tối từ localStorage trước khi render nội dung. */}
        <ThemeInit />
        {children}
      </body>
    </html>
  );
}
