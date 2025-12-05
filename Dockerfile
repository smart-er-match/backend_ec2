FROM python:3.10-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# GDAL 및 PostGIS 의존성 설치
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    binutils \
    libproj-dev \
    gdal-bin \
    libgdal-dev \
    python3-gdal \
 && rm -rf /var/lib/apt/lists/*

# GDAL 경로를 시스템이 확실히 찾을 수 있도록 심볼릭 링크 생성
# debian:trixie(slim) 환경의 실제 위치를 찾아 링크
RUN ln -sf /usr/lib/x86_64-linux-gnu/libgdal.so.36 /usr/lib/libgdal.so && \
    ln -sf /usr/lib/x86_64-linux-gnu/libgeos_c.so.1 /usr/lib/libgeos_c.so

# 장고를 위한 환경변수 고정
ENV GDAL_LIBRARY_PATH=/usr/lib/libgdal.so
ENV GEOS_LIBRARY_PATH=/usr/lib/libgeos_c.so

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# --preload: 마스터 프로세스에서 앱(모델)을 로드하여 워커 간 메모리 공유
# --workers: CPU 코어 수에 맞춰 4개로 설정
CMD ["gunicorn", "Finalproject.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "4", "--preload", "--timeout", "120"]