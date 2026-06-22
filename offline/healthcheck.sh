#!/usr/bin/env sh
# ============================================================
#  healthcheck.sh
#  ตรวจสุขภาพระบบ SeamlessFordMIS แบบละเอียด (Linux / macOS)
#  แสดง: Docker, containers, HTTP endpoints, volumes
#
#  Exit codes:
#    0 = ทุกอย่าง OK
#    1 = พบปัญหาร้ายแรง (FAIL)
#    2 = ระบบยังไม่ start (WARN only)
# ============================================================
set -eu
cd "$(dirname "$0")/.."

FAIL=0
WARN=0

echo ""
echo " ============================================================"
echo "  SeamlessFordMIS — Health Check"
echo " ============================================================"
echo ""

# ── 1. Docker Engine ─────────────────────────────────────────
echo " [1/5] Docker Engine"
if ! command -v docker >/dev/null 2>&1; then
    echo "        FAIL  ไม่พบ docker ใน PATH"
    echo "               ติดตั้ง Docker Engine แล้ว PATH ให้ถูกต้อง"
    exit 1
fi
if ! docker info >/dev/null 2>&1; then
    echo "        FAIL  Docker daemon ยังไม่ทำงาน"
    echo "               เปิด Docker Desktop (macOS/Windows) หรือ: sudo systemctl start docker"
    exit 1
fi
echo "        OK    Docker Engine พร้อมใช้งาน"

# ── 2. Container status ──────────────────────────────────────
echo ""
echo " [2/5] Container Status"
docker compose ps --format "table {{.Service}}\t{{.Status}}" 2>/dev/null || true
echo ""

ALL_HEALTHY=1
for svc in db backend nginx; do
    if ! docker compose ps "$svc" 2>/dev/null | grep -qi healthy; then
        echo "        WARN  $svc — ไม่ healthy"
        ALL_HEALTHY=0
        WARN=$((WARN + 1))
    else
        echo "        OK    $svc — healthy"
    fi
done

if [ "$ALL_HEALTHY" = "1" ]; then
    echo ""
    echo "        ผลรวม: บริการหลักทุกตัว healthy"
else
    echo ""
    echo "        ผลรวม: มีบริการที่ยังไม่ healthy"
    echo "                ดู log ด้วย: docker compose logs <service>"
fi

# ── 3. HTTP Endpoints ─────────────────────────────────────────
echo ""
echo " [3/5] HTTP Endpoints"

HTTP_PORT=80
if [ -f .env ]; then
    HTTP_PORT_ENV=$(grep "^HTTP_PORT=" .env 2>/dev/null | cut -d= -f2 | tr -d '[:space:]')
    if [ -n "$HTTP_PORT_ENV" ]; then
        HTTP_PORT="$HTTP_PORT_ENV"
    fi
fi

# Backend health (ผ่าน docker exec)
if docker compose exec -T backend curl -fsS http://localhost:8010/health >/dev/null 2>&1; then
    echo "        OK    Backend /health"
else
    echo "        FAIL  Backend /health ไม่ตอบสนอง"
    FAIL=$((FAIL + 1))
fi

# nginx (ผ่าน host port)
if curl -fsS --max-time 5 "http://localhost:${HTTP_PORT}/healthz" >/dev/null 2>&1; then
    echo "        OK    nginx port ${HTTP_PORT}  (http://localhost:${HTTP_PORT})"
elif curl -fsS --max-time 5 "http://localhost:${HTTP_PORT}" >/dev/null 2>&1; then
    echo "        OK    nginx port ${HTTP_PORT}  (http://localhost:${HTTP_PORT})"
else
    echo "        WARN  nginx port ${HTTP_PORT} — ไม่ตอบสนอง (curl ไม่พบหรือ port ยังไม่พร้อม)"
    WARN=$((WARN + 1))
fi

# API Smoke Test
if docker compose exec -T backend curl -fsS --max-time 5 "http://localhost:8010/api/system/status" >/dev/null 2>&1; then
    echo "        OK    API /api/system/status"
else
    echo "        FAIL  API /api/system/status — ไม่ตอบสนอง"
    FAIL=$((FAIL + 1))
fi

# ── 4. Docker Volumes ─────────────────────────────────────────
echo ""
echo " [4/5] Docker Volumes"
docker volume ls --filter name=seamlessfordmis 2>/dev/null | grep -v "VOLUME NAME" || echo "        (ไม่พบ seamlessfordmis volumes)"

# ── 5. Disk space (backup folder) ────────────────────────────
echo ""
echo " [5/5] Disk Space (data/backups)"
if [ -d data/backups ] && [ "$(ls -A data/backups 2>/dev/null)" ]; then
    BACKUP_SIZE=$(du -sh data/backups 2>/dev/null | cut -f1)
    echo "        ขนาดสำรองข้อมูลสะสม: ${BACKUP_SIZE}"
else
    echo "        ยังไม่มีไฟล์สำรอง"
fi

echo ""
echo " ============================================================"
echo "  Health check เสร็จสิ้น"
echo " ============================================================"
echo ""

if [ "$FAIL" -gt 0 ]; then
    exit 1
elif [ "$WARN" -gt 0 ]; then
    exit 2
else
    exit 0
fi
