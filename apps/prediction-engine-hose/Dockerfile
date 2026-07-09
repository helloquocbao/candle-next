FROM python:3.11.10-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ src/

RUN useradd --create-home --shell /usr/sbin/nologin appuser
USER appuser

CMD ["python", "src/main.py"]
