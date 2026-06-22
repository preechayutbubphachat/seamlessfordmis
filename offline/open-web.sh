#!/usr/bin/env sh
# ============================================================
#  SeamlessFordMIS — เปิดเว็บในเบราว์เซอร์ (Linux/macOS)
#  รองรับ macOS (open), Linux (xdg-open), fallback พิมพ์ URL
# ============================================================
set -eu
cd "$(dirname "$0")/.."

# อ่าน HTTP_PORT จาก .env
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

echo "เปิดเว็บ SeamlessFordMIS..."
echo "URL: $URL"
echo ""

# เปิดเบราว์เซอร์ตามระบบปฏิบัติการ
if command -v open >/dev/null 2>&1; then
  # macOS
  open "$URL"
elif command -v xdg-open >/dev/null 2>&1; then
  # Linux (desktop environment)
  xdg-open "$URL" >/dev/null 2>&1 &
elif command -v sensible-browser >/dev/null 2>&1; then
  # Debian/Ubuntu fallback
  sensible-browser "$URL" >/dev/null 2>&1 &
else
  echo "ไม่พบคำสั่งเปิดเบราว์เซอร์อัตโนมัติ"
  echo "กรุณาเปิดเบราว์เซอร์แล้วไปที่: $URL"
fi
