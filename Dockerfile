FROM python:3.12-slim

RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc libpq-dev libffi-dev g++ && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY nexus/ ./nexus/

ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app
ENV PORT=8080

CMD uvicorn nexus.main:app --host 0.0.0.0 --port ${PORT}
