# infra/ci-cd

Script/config hỗ trợ deploy (vd: `deploy.sh` SSH lên VPS, build tag Docker image theo app).

Lưu ý: các workflow GitHub Actions thực tế nằm ở `.github/workflows/` (bắt buộc theo yêu cầu GitHub),
mỗi app một file, chỉ trigger khi path của app đó (+ packages liên quan) thay đổi — team A merge code
không kích hoạt build/deploy của team B.
