# frontend (Next.js — App Router)

SPA + landing thương mại cho Crypto/HOSE Predictor. Migrate từ Vite vanilla
sang **Next.js 14 (App Router, JavaScript)**.

## Cấu trúc
```
app/
  layout.jsx          # root layout + ThemeInit
  page.jsx            # landing "/" (server component, SEO)
  app/page.jsx        # "/app" biểu đồ (client, dynamic ssr:false)
  about|terms|privacy|contact/page.jsx   # trang tĩnh (LegalShell)
  globals.css         # style dùng chung (port từ main.css)
components/           # ChartApp, TickerTape, MarketList, ThemeToggle, SiteFooter, LegalShell
lib/                  # chartRenderer, wsClient, apiClient, preferences, marketData, format
```

## Dev
```bash
cp .env.example .env.local   # trỏ NEXT_PUBLIC_API_BASE_URL / NEXT_PUBLIC_WS_URL
npm install && npm run dev   # http://localhost:3000
```
Backend chạy qua `infra/docker` (nginx cổng 80). Lưu ý CORS: api-gateway phải
whitelist origin dev (`http://localhost:3000`) trong `CORS_ORIGIN` (.env).

## Deploy Vercel
Vercel tự nhận diện Next.js. Set `NEXT_PUBLIC_API_BASE_URL` / `NEXT_PUBLIC_WS_URL`
trỏ domain backend thật (VPS + nginx + SSL) trong Project Settings.

## Env
- `NEXT_PUBLIC_API_BASE_URL` — REST base (vd `https://api.yourdomain.com`).
- `NEXT_PUBLIC_WS_URL` — WebSocket (vd `wss://api.yourdomain.com/ws`).
