import SiteFooter from "./SiteFooter";

// Khung chung cho các trang tĩnh pháp lý.
export default function LegalShell({ title, updated, children }) {
  return (
    <div id="app">
      <header className="site-header">
        <a className="brand" href="/">
          <span className="brand-mark">Cp</span>
          <span>CryptoPredict</span>
        </a>
        <nav className="main-nav" aria-label="Điều hướng chính">
          <a href="/">Trang chủ</a>
          <a href="/app">Biểu đồ</a>
        </nav>
      </header>
      <main className="legal-page">
        <article className="card legal-content">
          <p className="legal-back"><a href="/app">← Về trang biểu đồ</a></p>
          <h1>{title}</h1>
          {updated ? <p className="legal-updated">{updated}</p> : null}
          {children}
        </article>
      </main>
      <SiteFooter full={false} />
    </div>
  );
}
