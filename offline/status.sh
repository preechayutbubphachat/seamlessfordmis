#!/usr/bin/env sh
set -eu
cd "$(dirname "$0")/.."

# ---- ตรวจสอบ Docker ----
command -v docker >/dev/null 2>&1 || {
  echo "[ERROR] ไม่พบ Docker กรุณาติดตั้ง Docker Engine ก่อน"
  exit 1
}
docker info >/dev/null 2>&1 || {
  echo "[WARN] Docker ยังไม่ทำงาน กรุณาเริ่ม Docker daemon ก่อน"
  exit 1
}

# ---- อ่าน HTTP_PORT จาก .env ----
HTTP_PORT="80"
if [ -f ".env" ]; then
  set -a
  # shellcheck disable=SC1091
  . ./.env
  set +a
fi
HTTP_PORT="${HTTP_PORT:-80}"
if [ "$HTTP_PORT" = "80" ]; then
  URL="http://localhost"
else
  URL="http://localhost:${HTTP_PORT}"
fi

echo ""
echo "============================================================"
echo " SeamlessFordMIS — สถานะระบบ"
echo "============================================================"
echo ""

docker compose ps

echo ""
echo "Health checks:"
docker compose ps db      2>/dev/null | grep -qi healthy && echo "  db:      healthy" || echo "  db:      ไม่ healthy"
docker compose ps backend 2>/dev/null | grep -qi healthy && echo "  backend: healthy" || echo "  backend: ไม่ healthy"
docker compose ps nginx   2>/dev/null | grep -qi healthy && echo "  nginx:   healthy" || echo "  nginx:   ไม่ healthy"

echo ""
echo " URL เว็บ: $URL"
echo ""
echo " ถ้าระบบไม่ทำงาน: sh offline/start.sh   — เพื่อเริ่มระบบ"
echo " ดู log:          docker compose logs <service>"
echo " ตรวจสอบละเอียด: sh offline/healthcheck.sh"
