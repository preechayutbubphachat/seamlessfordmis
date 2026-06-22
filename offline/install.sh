#!/usr/bin/env sh
set -eu
cd "$(dirname "$0")/.."

command -v docker >/dev/null 2>&1 || {
  echo "Docker was not found. Install Docker Engine first."
  exit 1
}

docker info >/dev/null 2>&1 || {
  echo "Docker is not running."
  exit 1
}

if [ ! -f .env ]; then
  cp .env.offline.example .env
  echo "Created .env from .env.offline.example"
  echo "Edit .env and change POSTGRES_PASSWORD before real production use."
fi

mkdir -p data/backups

# ตรวจสอบว่า images มีอยู่แล้วหรือไม่
# ถ้ามีครบทั้ง 4 ตัว (เช่น หลัง load-images.sh) ข้ามขั้นตอน build
IMAGES_READY=1
for img in seamlessfordmis-backend:latest seamlessfordmis-frontend:latest postgres:16 nginx:alpine; do
    if ! docker image inspect "$img" >/dev/null 2>&1; then
        IMAGES_READY=0
        break
    fi
done

if [ "$IMAGES_READY" = "1" ]; then
    echo "Images already present in Docker — skipping build step."
    echo "(หาก images ไม่ถูกต้อง รัน offline/build-images.sh เพื่อ rebuild)"
else
    # ถ้าพบไฟล์ tar ใน images/ → โหลดจาก offline package ก่อน
    if [ -f "images/seamlessfordmis-backend.tar" ] || [ -f "images/seamlessfordmis-frontend.tar" ]; then
        echo "พบไฟล์ tar ใน images/ กำลังโหลด Docker images จาก offline package..."
        sh offline/load-images.sh
    else
        echo "Building Docker images... (ต้องการ internet และ source code)"
        docker compose build
    fi
fi

docker compose up -d db

echo "Waiting for database health..."
i=0
while [ "$i" -lt 60 ]; do
  if docker compose ps db | grep -qi healthy; then
    break
  fi
  i=$((i + 1))
  sleep 2
done

docker compose ps db | grep -qi healthy || {
  echo "Database did not become healthy in time."
  docker compose ps
  exit 1
}

sh offline/migrate.sh
docker compose up -d
docker compose ps
