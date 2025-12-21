FROM python:3.10-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y \
    build-essential \
    cmake \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# 모델이 마운트될 디렉토리 생성
RUN mkdir -p /app/models

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]

