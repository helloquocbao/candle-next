FROM python:3.11.10-slim

WORKDIR /app

# libgomp1: LightGBM (requirements.txt) can OpenMP runtime luc chay (khong
# chi luc build) — python:slim khong cai san, thieu se loi ngay khi import
# lightgbm ("libgomp.so.1: cannot open shared object file").
RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ src/

# Tạo user không đặc quyền để chạy service (Debian slim không có sẵn user
# "node" như alpine node image, nên tạo mới).
RUN useradd --create-home --shell /usr/sbin/nologin appuser

# Thu muc luu model ML da train (xem src/training/train_lightgbm.py), mount
# volume rieng trong docker-compose.yml. PHAI tao + chown truoc khi mount —
# Docker copy quyen/owner cua thu muc co san trong image sang volume rong
# luc mount lan dau; neu khong lam truoc, volume se thuoc root va appuser
# (user khong dac quyen o duoi) khong ghi duoc ("not available for writes").
RUN mkdir -p /app/trained_models && chown appuser:appuser /app/trained_models

USER appuser

CMD ["python", "src/main.py"]
