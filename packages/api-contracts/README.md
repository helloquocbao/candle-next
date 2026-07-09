# api-contracts

Nguồn chân lý (single source of truth) cho contract giữa các team — không phải code, chỉ là spec.

- `openapi.yaml` — REST API (frontend ⇄ api-gateway)
- `asyncapi.yaml` — WebSocket events (frontend ⇄ api-gateway)

Quy tắc: đổi field/endpoint ở đây trước, review chéo giữa team liên quan, rồi mới implement.
Đổi breaking change → bump version trong file + báo trong PR description.
