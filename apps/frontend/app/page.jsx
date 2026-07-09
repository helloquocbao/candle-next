import SiteFooter from "../components/SiteFooter";

// Landing page (/) — server component, tĩnh (tốt cho SEO/quảng cáo).
export default function LandingPage() {
  return (
    <div id="app" className="landing">
      <header className="site-header landing-header">
        <a className="brand" href="/">
          <span className="brand-mark">Cp</span>
          <span>CryptoPredict</span>
        </a>
        <nav className="main-nav" aria-label="Điều hướng chính">
          <a href="#features">Tính năng</a>
          <a href="#how">Cách hoạt động</a>
          <a href="#faq">FAQ</a>
        </nav>
        <div className="header-actions">
          <a href="/app" className="btn btn--primary btn--sm">Mở biểu đồ</a>
        </div>
      </header>

      {/* Hero */}
      <section className="hero">
        <div className="hero__content">
          <span className="eyebrow">Nền tảng phân tích crypto &amp; chứng khoán</span>
          <h1 className="hero__title">
            Dự đoán xu hướng thị trường<br />
            với <span className="grad-text">vùng nến AI</span> theo thời gian thực
          </h1>
          <p className="hero__subtitle">
            Theo dõi giá crypto và cổ phiếu HOSE real-time. Thuật toán tự học dựng dải
            giá dự đoán cho các nến kế tiếp, kèm chỉ số độ chính xác minh bạch — tất cả
            trong một biểu đồ.
          </p>
          <div className="hero__cta">
            <a href="/app" className="btn btn--primary btn--lg">Mở biểu đồ trực tiếp →</a>
            <a href="#how" className="btn btn--ghost btn--lg">Cách hoạt động</a>
          </div>
          <ul className="hero__points">
            <li>✓ Không cần đăng ký</li>
            <li>✓ Miễn phí</li>
            <li>✓ Crypto &amp; HOSE</li>
          </ul>
        </div>

        <div className="hero__panel" aria-hidden="true">
          <div className="panel-head">
            <span className="panel-pair"><span className="dot" /> BTC / USDT</span>
            <span className="panel-tf">1m · Live</span>
          </div>
          <div className="panel-chart">
            <svg viewBox="0 0 480 260" preserveAspectRatio="none" role="img">
              <defs>
                <linearGradient id="area" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#0f9d78" stopOpacity="0.45" />
                  <stop offset="100%" stopColor="#0f9d78" stopOpacity="0" />
                </linearGradient>
                <linearGradient id="cone" x1="0" y1="0" x2="1" y2="0">
                  <stop offset="0%" stopColor="#dd9a2e" stopOpacity="0.05" />
                  <stop offset="100%" stopColor="#dd9a2e" stopOpacity="0.3" />
                </linearGradient>
              </defs>
              <g stroke="#2a3142" strokeWidth="1">
                <line x1="0" y1="65" x2="480" y2="65" />
                <line x1="0" y1="130" x2="480" y2="130" />
                <line x1="0" y1="195" x2="480" y2="195" />
              </g>
              <path
                d="M24,210 L72,190 L120,200 L168,158 L216,170 L264,124 L300,138 L300,260 L24,260 Z"
                fill="url(#area)"
              />
              <path
                d="M24,210 L72,190 L120,200 L168,158 L216,170 L264,124 L300,138"
                fill="none"
                stroke="#0f9d78"
                strokeWidth="2.5"
                strokeLinejoin="round"
                strokeLinecap="round"
              />
              <path d="M300,138 L468,86 L468,168 Z" fill="url(#cone)" />
              <path
                d="M300,138 L468,120"
                fill="none"
                stroke="#dd9a2e"
                strokeWidth="2"
                strokeDasharray="5 5"
                strokeLinecap="round"
              />
              <circle cx="300" cy="138" r="4" fill="#0f9d78" />
              <circle cx="468" cy="120" r="4" fill="#dd9a2e" />
            </svg>
          </div>
          <div className="panel-chips">
            <span className="chip chip--up">▲ +2.41%</span>
            <span className="chip">Độ chính xác 68%</span>
            <span className="chip chip--forecast">Vùng dự đoán</span>
          </div>
        </div>
      </section>

      {/* Trust */}
      <section className="logos">
        <span className="logos__label">Nguồn dữ liệu real-time từ</span>
        <div className="logos__row">
          <span className="logo-pill">Binance</span>
          <span className="logo-pill">OKX</span>
          <span className="logo-pill">Bybit</span>
          <span className="logo-pill">HOSE</span>
        </div>
      </section>

      {/* Features */}
      <section id="features" className="section">
        <span className="eyebrow eyebrow--center">Tính năng</span>
        <h2 className="section__title">Mọi thứ để đọc thị trường, trong một trang</h2>
        <p className="section__subtitle">Không cài đặt, không đăng ký — mở là dùng.</p>
        <div className="feature-grid">
          <article className="feature">
            <span className="feature__icon">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"><path d="M3 3v18h18" /><polyline points="19 8 13 14 9 10 5 14" /></svg>
            </span>
            <h3>Biểu đồ nến real-time</h3>
            <p>Dữ liệu trực tiếp qua WebSocket, mượt như nền tảng giao dịch chuyên nghiệp.</p>
          </article>
          <article className="feature">
            <span className="feature__icon">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"><path d="M12 3l1.8 4.6L18.5 9.4l-4.7 1.8L12 16l-1.8-4.8L5.5 9.4l4.7-1.8L12 3z" /></svg>
            </span>
            <h3>Vùng dự đoán bằng AI</h3>
            <p>Thuật toán thống kê + máy học dựng dải giá dự đoán nhiều bước cho nến sắp tới.</p>
          </article>
          <article className="feature">
            <span className="feature__icon">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><circle cx="12" cy="12" r="9" /><circle cx="12" cy="12" r="5" /><circle cx="12" cy="12" r="1.4" fill="currentColor" /></svg>
            </span>
            <h3>Theo dõi độ chính xác</h3>
            <p>So sánh dự đoán với thực tế, hiển thị % chính xác — minh bạch, không tô hồng.</p>
          </article>
          <article className="feature">
            <span className="feature__icon">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"><path d="M21 12a9 9 0 1 1-2.6-6.3" /><polyline points="21 4 21 9 16 9" /></svg>
            </span>
            <h3>Tự học liên tục</h3>
            <p>Vòng lặp Genetic Algorithm tự tối ưu tham số theo diễn biến thị trường thực tế.</p>
          </article>
          <article className="feature">
            <span className="feature__icon">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="9" /><path d="M3 12h18" /><path d="M12 3c2.5 2.4 3.9 5.6 3.9 9s-1.4 6.6-3.9 9c-2.5-2.4-3.9-5.6-3.9-9S9.5 5.4 12 3z" /></svg>
            </span>
            <h3>Crypto &amp; Chứng khoán VN</h3>
            <p>Chuyển đổi giữa thị trường crypto (Binance/OKX/Bybit) và cổ phiếu HOSE.</p>
          </article>
          <article className="feature">
            <span className="feature__icon">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"><path d="M13 2 4 14h6l-1 8 9-12h-6l1-8z" /></svg>
            </span>
            <h3>Nhanh &amp; miễn phí</h3>
            <p>Không cần tài khoản, không cài đặt. Mở trình duyệt là dùng được ngay.</p>
          </article>
        </div>
      </section>

      {/* How */}
      <section id="how" className="section section--alt">
        <span className="eyebrow eyebrow--center">Quy trình</span>
        <h2 className="section__title">Ba bước, hoàn toàn tự động</h2>
        <div className="steps">
          <div className="step">
            <span className="step__num">1</span>
            <h3>Thu thập dữ liệu</h3>
            <p>Kết nối API công khai của các sàn/nguồn, chuẩn hoá và lưu nến real-time.</p>
          </div>
          <div className="step">
            <span className="step__num">2</span>
            <h3>Chạy thuật toán</h3>
            <p>Mô hình dự đoán các nến kế tiếp, tự đánh giá và tinh chỉnh theo thời gian.</p>
          </div>
          <div className="step">
            <span className="step__num">3</span>
            <h3>Hiển thị trực quan</h3>
            <p>Vẽ vùng giá dự đoán lên chart kèm chỉ số độ chính xác gần đây.</p>
          </div>
        </div>
      </section>

      {/* Metrics */}
      <section className="metrics">
        <div className="metric"><span className="metric__num">4+</span><span className="metric__label">Nguồn dữ liệu</span></div>
        <div className="metric"><span className="metric__num">24/7</span><span className="metric__label">Real-time</span></div>
        <div className="metric"><span className="metric__num">2</span><span className="metric__label">Thị trường</span></div>
        <div className="metric"><span className="metric__num">0đ</span><span className="metric__label">Miễn phí</span></div>
      </section>

      {/* FAQ */}
      <section id="faq" className="section">
        <span className="eyebrow eyebrow--center">FAQ</span>
        <h2 className="section__title">Câu hỏi thường gặp</h2>
        <div className="faq">
          <details className="faq__item">
            <summary>CryptoPredict có miễn phí không?</summary>
            <p>Có. Miễn phí hoàn toàn, không cần đăng ký. Duy trì qua quảng cáo và đóng góp tự nguyện.</p>
          </details>
          <details className="faq__item">
            <summary>Dự đoán có phải lời khuyên đầu tư không?</summary>
            <p>Không. Mọi dự đoán do thuật toán tạo ra, chỉ mang tính tham khảo và thử nghiệm.</p>
          </details>
          <details className="faq__item">
            <summary>Dữ liệu lấy từ đâu?</summary>
            <p>Từ API công khai của Binance, OKX, Bybit (crypto) và VNDIRECT (HOSE), chỉ để hiển thị.</p>
          </details>
          <details className="faq__item">
            <summary>Độ chính xác của dự đoán ra sao?</summary>
            <p>Chỉ số độ chính xác thực tế hiển thị ngay trên biểu đồ. Không mô hình nào đúng 100%.</p>
          </details>
        </div>
      </section>

      {/* CTA */}
      <section className="cta-band">
        <div className="cta-band__inner">
          <h2>Sẵn sàng quan sát thị trường?</h2>
          <p>Mở biểu đồ và xem vùng dự đoán ngay — không cần đăng ký.</p>
          <a href="/app" className="btn btn--light btn--lg">Mở biểu đồ ngay →</a>
        </div>
      </section>

      <SiteFooter />
    </div>
  );
}
