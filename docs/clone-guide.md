# Hướng dẫn clone theo team

Repo hiện là **1 monorepo** (`apps/frontend`, `apps/api-gateway`, `apps/ingestion-service`, `apps/prediction-engine`...).
Có 2 cách để mỗi team chỉ làm việc với phần của mình, tuỳ giai đoạn dự án.

---

## Giai đoạn 1-2: vẫn 1 repo — dùng `sparse-checkout`

Mỗi dev vẫn clone **chung 1 repo git**, nhưng máy chỉ tải/checkout đúng thư mục cần — không thấy code của team khác trong working directory, không cần đọc/động vào phần không liên quan.

### Team Frontend

```bash
git clone --filter=blob:none --sparse git@github.com:<org>/core-dev.git
cd core-dev
git sparse-checkout set apps/frontend packages/shared-types packages/api-contracts docs
```

### Team Backend (api-gateway + ingestion-service)

```bash
git clone --filter=blob:none --sparse git@github.com:<org>/core-dev.git
cd core-dev
git sparse-checkout set apps/api-gateway apps/ingestion-service packages/shared-types packages/api-contracts infra docs
```

### Team ML (prediction-engine)

```bash
git clone --filter=blob:none --sparse git@github.com:<org>/core-dev.git
cd core-dev
git sparse-checkout set apps/prediction-engine packages/api-contracts docs
```

**Vì sao vẫn nên có `packages/api-contracts` trong mọi lần checkout**: đây là hợp đồng API — team nào cũng cần đọc để biết mình gọi/trả gì, dù không đụng code của team khác.

**Ưu điểm**: 1 lịch sử git duy nhất, 1 chỗ PR, CODEOWNERS + CI theo path (đã cấu hình ở `.github/`) vẫn hoạt động bình thường, không tốn công đồng bộ nhiều repo.
**Nhược điểm**: vẫn phải xin quyền vào cùng 1 repo GitHub; không tách được quyền truy cập ở mức repo (ai cũng thấy được lịch sử commit của app khác nếu cố tình `sparse-checkout set` lại).

`--filter=blob:none` giúp không tải nội dung file của các app khác về máy (chỉ tải khi thực sự checkout), nên repo lớn cũng không nặng ổ đĩa/băng thông.

---

## Giai đoạn 3: tách hẳn thành nhiều repo

Khi cần tách quyền truy cập thật sự (team ngoài không được thấy code app khác) hoặc quy mô đủ lớn để mỗi team có repo, CI/CD, quy trình release riêng:

```bash
# Tách apps/frontend thành repo riêng, giữ nguyên lịch sử commit của thư mục đó
git subtree split --prefix=apps/frontend -b frontend-only
git push git@github.com:<org>/crypto-predictor-frontend.git frontend-only:main
```

Lặp lại cho `apps/api-gateway`, `apps/ingestion-service`, `apps/prediction-engine`.

Sau khi tách:
- Mỗi team `git clone` đúng 1 repo của mình — không còn thấy code app khác nữa.
- `packages/shared-types` và `packages/api-contracts` publish thành package versioned (npm/PyPI riêng), các repo mới `npm install`/`pip install` thay vì import đường dẫn tương đối.
- `infra/` tách thành repo platform riêng do team platform sở hữu.

## Chọn giai đoạn nào?

| Số team | Khuyến nghị |
|---|---|
| 1 team (hiện tại) | Clone full, không cần sparse-checkout |
| 2-3 team, tin tưởng nhau, muốn CI/PR tập trung | `sparse-checkout` (Giai đoạn 1-2) |
| Nhiều team, cần tách quyền truy cập/release độc lập | Tách repo (Giai đoạn 3) |
