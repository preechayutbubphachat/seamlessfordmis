#!/usr/bin/env sh
# ============================================================
#  SeamlessFordMIS — สำรองข้อมูลก่อนอัปเดตระบบ (Linux/macOS)
#  ควรรันทุกครั้งก่อนที่จะ:
#    - อัปเดต Docker images เป็นเวอร์ชันใหม่
#    - รัน database migration
#    - เปลี่ยน configuration สำคัญ
#    - ถอนการติดตั้งและติดตั้งใหม่
# ============================================================
set -eu
cd "$(dirname "$0")/.."

echo "============================================================"
echo " SeamlessFordMIS — สำรองข้อมูลก่อนอัปเดตระบบ"
echo "============================================================"
echo ""
echo " สคริปต์นี้สำรองข้อมูลทั้งหมดก่อนทำการอัปเดตหรืออัปเกรดระบบ"
echo " ควรรันทุกครั้งก่อนที่จะ:"
echo "   - อัปเดต Docker images เป็นเวอร์ชันใหม่"
echo "   - รัน database migration"
echo "   - เปลี่ยน configuration สำคัญ"
echo "   - ถอนการติดตั้งและติดตั้งใหม่"
echo ""

# ---- ตรวจสอบ Docker ----
if ! command -v docker >/dev/null 2>&1; then
  echo "[ERROR] ไม่พบ Docker กรุณาเปิด Docker Engine ก่อน"
  exit 1
fi
if ! docker info >/dev/null 2>&1; then
  echo "[ERROR] Docker ยังไม่ทำงาน กรุณาเริ่ม Docker daemon แล้วรอจนพร้อม"
  exit 1
fi
echo "[OK] Docker พร้อมทำงาน"

# ---- ตรวจสอบว่า container db กำลังทำงาน ----
echo ""
echo "[INFO] ตรวจสอบสถานะ containers..."

SKIP_DB_DUMP=0
if ! docker compose ps --services --filter "status=running" 2>/dev/null | grep -qi "^db$"; then
  echo ""
  echo "[WARNING] Container db ไม่ได้ทำงานอยู่"
  echo "          ไม่สามารถ dump ฐานข้อมูลได้หาก db ไม่ทำงาน"
  echo ""
  echo " ตัวเลือก:"
  echo "   1. เริ่มระบบก่อนด้วย offline/start.sh แล้วรันสคริปต์นี้ใหม่"
  echo "   2. สำรองเฉพาะ Docker volumes โดยไม่มี database dump"
  echo ""
  printf "ต้องการสำรองเฉพาะ Docker volumes โดยไม่มี database dump หรือไม่? (y/N): "
  read -r CHOICE
  case "$CHOICE" in
    y|Y)
      SKIP_DB_DUMP=1
      ;;
    *)
      echo ""
      echo "  ยกเลิก กรุณาเริ่มระบบก่อนแล้วรันสคริปต์นี้ใหม่"
      echo ""
      exit 1
      ;;
  esac
else
  echo "[OK] Container db กำลังทำงาน"
fi

# ---- อ่านค่าจาก .env ----
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

# ---- สร้าง timestamp และ backup directory ----
STAMP="$(date +%Y%m%d-%H%M%S)"
BACKUP_DIR="data/backups/pre-update-${STAMP}"

echo ""
echo "[INFO] สร้างโฟลเดอร์สำรอง: $BACKUP_DIR"
mkdir -p "$BACKUP_DIR" || {
  echo "[ERROR] ไม่สามารถสร้างโฟลเดอร์ $BACKUP_DIR ได้"
  exit 1
}

BACKUP_OK=1

# ---- Step 1: Database dump ----
echo ""
if [ "$SKIP_DB_DUMP" -eq 1 ]; then
  echo "[SKIP] ข้ามการ dump ฐานข้อมูล (container db ไม่ได้ทำงาน)"
else
  echo "[STEP 1/5] กำลัง dump ฐานข้อมูล PostgreSQL..."
  if docker compose exec -T db pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" > "$BACKUP_DIR/database.sql" 2>/dev/null; then
    echo "[OK]   dump ฐานข้อมูลสำเร็จ"
  else
    echo "[ERROR] Dump ฐานข้อมูลล้มเหลว"
    echo "        ตรวจสอบว่า container db ทำงานปกติ: docker compose ps"
    BACKUP_OK=0
  fi
fi

# ---- Step 2: source_data volume ----
echo ""
echo "[STEP 2/5] กำลังสำรอง volume source_data..."
if docker run --rm \
  -v seamlessfordmis_source_data:/source_data:ro \
  -v "$(pwd)/$BACKUP_DIR":/backup \
  nginx:alpine tar -czf /backup/source_data.tar.gz -C / source_data 2>/dev/null; then
  echo "[OK]   source_data.tar.gz สำเร็จ"
else
  echo "[WARNING] สำรอง source_data ล้มเหลว (อาจยังไม่มีข้อมูล)"
fi

# ---- Step 3: uploads volume ----
echo ""
echo "[STEP 3/5] กำลังสำรอง volume uploads..."
if docker run --rm \
  -v seamlessfordmis_uploads:/uploads:ro \
  -v "$(pwd)/$BACKUP_DIR":/backup \
  nginx:alpine tar -czf /backup/uploads.tar.gz -C / uploads 2>/dev/null; then
  echo "[OK]   uploads.tar.gz สำเร็จ"
else
  echo "[WARNING] สำรอง uploads ล้มเหลว (อาจยังไม่มีข้อมูล)"
fi

# ---- Step 4: reports volume ----
echo ""
echo "[STEP 4/5] กำลังสำรอง volume reports..."
if docker run --rm \
  -v seamlessfordmis_reports:/reports:ro \
  -v "$(pwd)/$BACKUP_DIR":/backup \
  nginx:alpine tar -czf /backup/reports.tar.gz -C / reports 2>/dev/null; then
  echo "[OK]   reports.tar.gz สำเร็จ"
else
  echo "[WARNING] สำรอง reports ล้มเหลว (อาจยังไม่มีข้อมูล)"
fi

# ---- Step 4b: logs volume ----
echo ""
echo "[STEP 4b] กำลังสำรอง volume logs..."
if docker run --rm \
  -v seamlessfordmis_logs:/logs:ro \
  -v "$(pwd)/$BACKUP_DIR":/backup \
  nginx:alpine tar -czf /backup/logs.tar.gz -C / logs 2>/dev/null; then
  echo "[OK]   logs.tar.gz สำเร็จ"
else
  echo "[WARNING] สำรอง logs ล้มเหลว (อาจยังไม่มีข้อมูล)"
fi

# ---- Step 5: คัดลอก .env ----
echo ""
echo "[STEP 5/5] สำรองไฟล์ตั้งค่า .env..."
if [ -f ".env" ]; then
  cp ".env" "$BACKUP_DIR/.env.bak"
  echo "[OK]   .env.bak สำเร็จ"
else
  echo "[WARNING] ไม่พบ .env"
fi

# ---- สรุป ----
echo ""
echo "============================================================"
if [ "$BACKUP_OK" -eq 1 ]; then
  echo " สำรองข้อมูลก่อนอัปเดตเสร็จสิ้น"
else
  echo " สำรองข้อมูลเสร็จสิ้น (มีบางส่วนล้มเหลว — ดูข้อความด้านบน)"
fi
echo "============================================================"
echo ""
echo " ที่เก็บข้อมูลสำรอง: $BACKUP_DIR/"
echo ""
echo " ไฟล์ที่สำรอง:"
[ -f "$BACKUP_DIR/database.sql" ]        && echo "   • database.sql         (ฐานข้อมูลผู้ป่วย)"
[ -f "$BACKUP_DIR/source_data.tar.gz" ] && echo "   • source_data.tar.gz   (ข้อมูลต้นทาง)"
[ -f "$BACKUP_DIR/uploads.tar.gz" ]     && echo "   • uploads.tar.gz       (ไฟล์ที่อัปโหลด)"
[ -f "$BACKUP_DIR/reports.tar.gz" ]     && echo "   • reports.tar.gz       (รายงาน)"
[ -f "$BACKUP_DIR/logs.tar.gz" ]        && echo "   • logs.tar.gz          (Logs)"
[ -f "$BACKUP_DIR/.env.bak" ]           && echo "   • .env.bak             (ไฟล์ตั้งค่า)"
echo ""
echo "============================================================"
echo " [!] ข้อมูลสำรองมีข้อมูลผู้ป่วย — เก็บในพื้นที่ปลอดภัยภายในหน่วยงาน"
echo "     ห้ามส่งออกนอกเครือข่ายโรงพยาบาล ห้าม upload ขึ้น cloud สาธารณะ"
echo "============================================================"
echo ""
echo " ขั้นตอนต่อไป — ดำเนินการอัปเดตได้เลย:"
echo "   1. รัน offline/stop.sh เพื่อหยุดระบบ"
echo "   2. ดำเนินการอัปเดต (เปลี่ยน images หรือรัน migration)"
echo "   3. รัน offline/start.sh เพื่อเริ่มระบบใหม่"
echo "   4. หากมีปัญหา ใช้ไฟล์สำรองใน $BACKUP_DIR/ เพื่อกู้คืน"
echo ""
