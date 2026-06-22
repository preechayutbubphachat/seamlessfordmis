#!/usr/bin/env sh
set -eu
cd "$(dirname "$0")/.."

# ---- ตรวจสอบ Docker ----
command -v docker >/dev/null 2>&1 || {
  echo "[ERROR] ไม่พบ Docker กรุณาติดตั้ง Docker Engine ก่อน"
  exit 1
}
docker info >/dev/null 2>&1 || {
  echo "[WARN] Docker ยังไม่ทำงาน — containers อาจหยุดอยู่แล้ว"
}

echo "กำลังหยุดระบบ SeamlessFordMIS..."
docker compose down

echo ""
echo "[OK] หยุดระบบเรียบร้อยแล้ว"
echo "     ข้อมูลทั้งหมดยังอยู่ใน Docker volumes ครบถ้วน"
echo "     รัน offline/start.sh เพื่อเริ่มระบบอีกครั้ง"
