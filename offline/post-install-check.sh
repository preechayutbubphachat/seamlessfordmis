#!/usr/bin/env sh
# ============================================================
#  SeamlessFordMIS — ตรวจสอบระบบหลังติดตั้ง (Linux/macOS)
#  ใช้หลังรัน offline/install.sh หรือหลังติดตั้งใหม่
#  exit 0 = ผ่านทั้งหมด, exit 1 = มีปัญหา, exit 2 = คำเตือนเท่านั้น
# ============================================================
set -eu
cd "$(dirname "$0")/.."

PASS=0
FAIL=0
WARN=0

# ---- ฟังก์ชันสรุปผล ----
print_summary() {
  echo ""
  echo "============================================================"
  echo " สรุปผลการตรวจสอบ"
  echo "============================================================"
  echo ""
  echo " ผ่าน (PASS)    : $PASS"
  echo " คำเตือน (WARN) : $WARN"
  echo " ล้มเหลว (FAIL) : $FAIL"
  echo ""
  if [ "$FAIL" -eq 0 ] && [ "$WARN" -eq 0 ]; then
    echo " [OK] ระบบพร้อมใช้งานสมบูรณ์"
  elif [ "$FAIL" -eq 0 ]; then
    echo " [WARN] ระบบยังไม่ได้เริ่มทำงาน — รัน offline/install.sh เพื่อเริ่มระบบ"
  else
    echo " [FAIL] พบปัญหาที่ต้องแก้ไข — ดูรายละเอียดด้านบน"
  fi
  echo ""
  echo "============================================================"
  echo ""
}

echo "============================================================"
echo " SeamlessFordMIS — ตรวจสอบระบบหลังติดตั้ง"
echo "============================================================"
echo ""

# ---- [1] Docker ติดตั้งอยู่หรือไม่ ----
echo "[ตรวจสอบ 1/7] Docker ติดตั้งอยู่หรือไม่..."
if ! command -v docker >/dev/null 2>&1; then
  echo "[FAIL] ไม่พบ Docker"
  echo "       กรุณาติดตั้ง Docker Engine จาก https://docs.docker.com/engine/install/"
  FAIL=$((FAIL + 1))
  print_summary
  exit 1
fi
echo "[OK]   Docker พบที่ระบบ"
PASS=$((PASS + 1))

# ---- [2] Docker Engine กำลังทำงานหรือไม่ ----
echo ""
echo "[ตรวจสอบ 2/7] Docker Engine กำลังทำงานหรือไม่..."
if ! docker info >/dev/null 2>&1; then
  echo "[FAIL] Docker Engine ยังไม่ทำงาน กรุณาเริ่ม Docker daemon ก่อน"
  FAIL=$((FAIL + 1))
  print_summary
  exit 1
fi
echo "[OK]   Docker Engine พร้อมทำงาน"
PASS=$((PASS + 1))

# ---- [3] ไฟล์ตั้งค่า .env ----
echo ""
echo "[ตรวจสอบ 3/7] ไฟล์ตั้งค่า .env..."
if [ ! -f ".env" ]; then
  echo "[FAIL] ไม่พบไฟล์ .env"
  echo "       คัดลอก .env.offline.example มาเป็น .env แล้วแก้รหัสผ่าน"
  FAIL=$((FAIL + 1))
else
  echo "[OK]   พบไฟล์ .env"
  PASS=$((PASS + 1))
fi

# ---- [4] Docker images ถูกโหลดแล้วหรือไม่ ----
echo ""
echo "[ตรวจสอบ 4/7] Docker images..."
IMG_FAIL=0

for img in "postgres:16" "nginx:alpine" "seamlessfordmis-backend:latest" "seamlessfordmis-frontend:latest"; do
  if docker image inspect "$img" >/dev/null 2>&1; then
    echo "[OK]   $img"
  else
    echo "[FAIL] ไม่พบ image: $img"
    IMG_FAIL=1
  fi
done

if [ "$IMG_FAIL" -eq 1 ]; then
  echo ""
  echo "       หาก images ไม่ครบ ให้รัน offline/load-images.sh เพื่อโหลด images"
  FAIL=$((FAIL + 1))
else
  PASS=$((PASS + 1))
fi

# ---- [5] Containers กำลังทำงานหรือไม่ ----
echo ""
echo "[ตรวจสอบ 5/7] Containers กำลังทำงานหรือไม่..."
CONTAINERS_RUNNING=0

for svc in db backend frontend nginx; do
  if docker compose ps --services --filter "status=running" 2>/dev/null | grep -qi "^${svc}$"; then
    echo "[OK]   $svc"
    CONTAINERS_RUNNING=1
  else
    echo "[WARN] Container $svc ยังไม่ทำงาน"
  fi
done

if [ "$CONTAINERS_RUNNING" -eq 0 ]; then
  echo ""
  echo "       Containers ยังไม่ทำงาน นี่เป็นเรื่องปกติในการติดตั้งครั้งแรก"
  echo "       กรุณารัน offline/install.sh เพื่อเริ่มระบบ"
  echo "       การตรวจสอบขั้นต่อไป (ฐานข้อมูล+เว็บ) จะถูกข้ามไป"
  WARN=$((WARN + 1))
  print_summary
  exit 2
fi
PASS=$((PASS + 1))

# ---- [6] ฐานข้อมูล PostgreSQL ----
echo ""
echo "[ตรวจสอบ 6/7] ฐานข้อมูล PostgreSQL..."

POSTGRES_USER="seamlessfordmis"
POSTGRES_DB="seamlessfordmis"
if [ -f ".env" ]; then
  set -a
  # shellcheck disable=SC1091
  . ./.env
  set +a
fi
POSTGRES_USER="${POSTGRES_USER:-seamlessfordmis}"
POSTGRES_DB="${POSTGRES_DB:-seamlessfordmis}"

if docker compose exec -T db pg_isready -U "$POSTGRES_USER" -d "$POSTGRES_DB" >/dev/null 2>&1; then
  echo "[OK]   ฐานข้อมูลพร้อมทำงาน"
  PASS=$((PASS + 1))
else
  echo "[FAIL] ฐานข้อมูลยังไม่พร้อม"
  echo "       รอสักครู่แล้วลองใหม่ หรือดู log ด้วย: docker compose logs db"
  FAIL=$((FAIL + 1))
fi

# ---- [7] Web endpoint ----
echo ""
echo "[ตรวจสอบ 7/7] Web endpoint..."

HTTP_PORT="${HTTP_PORT:-80}"
if [ "$HTTP_PORT" = "80" ]; then
  URL="http://localhost"
else
  URL="http://localhost:${HTTP_PORT}"
fi

if ! command -v curl >/dev/null 2>&1; then
  echo "[WARN] ไม่พบ curl — ข้ามการตรวจสอบเว็บ (ติดตั้ง curl เพื่อตรวจสอบครบถ้วน)"
  WARN=$((WARN + 1))
else
  STATUS=$(curl -s -o /dev/null -w "%{http_code}" --max-time 5 "${URL}/healthz" 2>/dev/null || echo "000")
  if [ "$STATUS" = "200" ]; then
    echo "[OK]   เว็บพร้อมใช้งานที่ $URL"
    PASS=$((PASS + 1))
  else
    STATUS=$(curl -s -o /dev/null -w "%{http_code}" --max-time 5 "${URL}" 2>/dev/null || echo "000")
    case "$STATUS" in
      2*|3*)
        echo "[OK]   เว็บพร้อมใช้งานที่ $URL"
        PASS=$((PASS + 1))
        ;;
      *)
        echo "[FAIL] ไม่สามารถเชื่อมต่อเว็บได้ที่ $URL (HTTP $STATUS)"
        echo "       รอให้ containers พร้อมทำงานแล้วลองใหม่ (ใช้เวลาประมาณ 1-2 นาที)"
        FAIL=$((FAIL + 1))
        ;;
    esac
  fi
fi

print_summary

if [ "$FAIL" -eq 0 ] && [ "$WARN" -eq 0 ]; then
  exit 0
elif [ "$FAIL" -eq 0 ]; then
  exit 2
else
  exit 1
fi
