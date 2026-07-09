# Crypto Real-time Predictor Chart

Xem `project_overview.md` (ý tưởng), `project_technical_spec.md` (kỹ thuật chi tiết), và `docs/clone-guide.md` (mỗi team clone/checkout phần nào).

## Cấu trúc thư mục

```
core-dev/
├── apps/                      # Các service độc lập, mỗi service 1 vòng đời riêng
│   ├── frontend/               # SPA — TradingView Lightweight Charts
│   ├── api-gateway/             # REST + WebSocket, cửa ngõ duy nhất cho FE
│   ├── ingestion-service/       # Kết nối Binance, ghi DB/Redis
│   └── prediction-engine/       # ML/Genetic Algorithm + self-learning loop
│
├── packages/                  # Code dùng chung, tránh lặp giữa các apps
│   ├── shared-types/            # Type/schema chung FE ⇄ BE
│   ├── api-contracts/           # openapi.yaml + asyncapi.yaml — nguồn chân lý về API
│   └── utils/                   # Helper dùng chung
│
├── infra/                     # Hạ tầng, không chứa business logic
│   ├── docker/                  # docker-compose.yml, Dockerfile, nginx
│   ├── db/                      # migrations SQL
│   └── ci-cd/                   # script deploy (workflow thật ở .github/workflows/)
│
├── .github/
│   ├── workflows/                # 1 workflow/app, chỉ chạy khi path app đó đổi
│   └── CODEOWNERS                # map thư mục → team, bắt buộc review đúng người
│
├── docs/                      # (để dành cho tài liệu mới; docs hiện có ở root)
├── scripts/                   # Script dev/seed/backtest thủ công
├── .env.example
└── project_overview.md, project_technical_spec.md, monetization_strategies.md
```

## Nguyên tắc tổ chức

- **Mỗi service trong `apps/` build & deploy độc lập** (Dockerfile riêng) — sửa `prediction-engine` không đụng tới `frontend`.
- **`api-gateway` là cửa ngõ duy nhất**: frontend không gọi thẳng `ingestion-service`/DB; các service backend không gọi thẳng nhau, giao tiếp qua Redis pub/sub hoặc DB.
- **`packages/` chỉ chứa code thuần, không chứa logic nghiệp vụ riêng của 1 service** — dùng để tránh lệch contract (vd: đổi field trong `Prediction` type chỉ cần sửa 1 nơi).
- **`infra/` tách biệt hoàn toàn khỏi `apps/`** — đổi hạ tầng (thêm service, đổi port) không cần sửa code ứng dụng.

## Chạy local

**Backend** (ingestion, prediction, api-gateway, DB, Redis, nginx):

```bash
cp .env.example .env
cd infra/docker && docker compose up --build
```

**Frontend** (Next.js — App Router) — deploy độc lập trên Vercel (không nằm trong docker-compose), chạy dev local bằng:

```bash
cd apps/frontend
cp .env.example .env.local
npm install && npm run dev   # http://localhost:3000
```

Trang chủ `/` là landing; biểu đồ (crypto + chứng khoán HOSE) ở `/app`.

## Lộ trình khi dự án phình ra & tách team

Cấu trúc `apps/*` theo ranh giới service đã được thiết kế sẵn để tách dần, không cần đảo lại từ đầu.

**Giai đoạn 1 — team nhỏ (hiện tại)**
Monorepo như trên là đủ, 1-2 dev đọc hết code không tốn công.

**Giai đoạn 2 — 2-3 team (FE, BE, ML), vẫn 1 repo**
Vấn đề lớn nhất lúc này không phải là *thư mục* mà là *ai được đổi gì mà không hỏi ai*:

- `.github/CODEOWNERS` — PR đụng `apps/frontend/` bắt buộc review bởi team frontend, đụng `apps/prediction-engine/` bắt buộc team ML, v.v. Đã tạo sẵn (đổi tên `@team-*` thành GitHub team thật).
- `.github/workflows/*.yml` — mỗi app 1 pipeline CI, chỉ trigger khi path của app đó thay đổi. Team BE merge code không kích hoạt build của team FE. Đã tạo sẵn 4 workflow tương ứng 4 app.
- `packages/api-contracts/` (openapi.yaml + asyncapi.yaml) — **hợp đồng** giữa các team. Team FE lập trình theo contract này, không cần đọc code `api-gateway`. Team BE đổi response phải sửa contract trước, review chéo, rồi mới implement. Đây là điểm mấu chốt để 2 team làm song song mà không giẫm chân.
- `packages/shared-types/` publish như package nội bộ (npm private registry/verdaccio) thay vì import đường dẫn tương đối, để version hoá được (team BE đổi type là breaking change, team FE biết ngay qua version bump).

**Giai đoạn 3 — nhiều team, cần tách repo riêng**
Vì mỗi `apps/*` đã độc lập (Dockerfile riêng, không import chéo ngoài `packages/`), tách thành repo riêng chỉ là kỹ thuật, không phải thiết kế lại:

- Dùng `git subtree split` (hoặc `git filter-repo`) để tách từng `apps/*` thành repo riêng, giữ nguyên lịch sử commit.
- `packages/shared-types` và `packages/api-contracts` publish thành package versioned (npm/PyPI) — các repo mới cài như dependency thay vì copy code.
- `infra/` tách thành repo "platform"/infra-as-code riêng, team platform sở hữu, các team app không tự đổi hạ tầng.
- Giữ 1 repo "docs/contracts" trung tâm (hoặc chính `packages/api-contracts` cũ) làm nơi các team tham chiếu chung, tránh mỗi repo tự vẽ lại API.

Tóm lại: điều quyết định khả năng mở rộng không phải là số lượng thư mục, mà là **ranh giới rõ + hợp đồng API rõ (contract-first)** — hai thứ này đã được dựng sẵn nên việc tách repo sau này chỉ là thao tác cơ học.
