#!/usr/bin/env sh
# ============================================================
#  SeamlessFordMIS — แสดง IP สำหรับเครื่องอื่นใน LAN
#  รองรับ Linux (hostname -I / ip addr) และ macOS (ifconfig)
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

echo ""
echo "============================================================"
echo " SeamlessFordMIS — IP สำหรับเครื่องอื่นใน LAN"
echo "============================================================"
echo ""
echo " IP ของเครื่องนี้ที่เครื่องอื่น LAN ใช้เข้าระบบได้:"
echo ""

FOUND=0

# Linux: hostname -I
if command -v hostname >/dev/null 2>&1 && hostname -I >/dev/null 2>&1; then
  for ip in $(hostname -I); do
    case "$ip" in
      127.*|::1) ;;
      *)
        FOUND=1
        if [ "$HTTP_PORT" = "80" ]; then
          echo "   $ip  >  http://$ip"
        else
          echo "   $ip  >  http://$ip:${HTTP_PORT}"
        fi
        ;;
    esac
  done
fi

# macOS fallback: ifconfig
if [ "$FOUND" -eq 0 ] && command -v ifconfig >/dev/null 2>&1; then
  ifconfig 2>/dev/null | grep "inet " | grep -v "127.0.0.1" | while IFS= read -r line; do
    ip=$(echo "$line" | awk '{print $2}' | sed 's/addr://')
    if [ -n "$ip" ]; then
      FOUND=1
      if [ "$HTTP_PORT" = "80" ]; then
        echo "   $ip  >  http://$ip"
      else
        echo "   $ip  >  http://$ip:${HTTP_PORT}"
      fi
    fi
  done
fi

if [ "$FOUND" -eq 0 ]; then
  echo "   ไม่สามารถหา IP อัตโนมัติได้"
  echo "   ตรวจสอบด้วย: ip addr  หรือ  ifconfig"
fi

echo ""
echo " วิธีใช้:"
echo "   1. บอก URL ด้านบนให้ผู้ใช้เครื่องอื่นใน LAN เดียวกัน"
echo "   2. ผู้ใช้เปิด browser พิมพ์ URL แล้วใช้งานได้ทันที"
echo ""
echo " ถ้าเข้าไม่ได้จากเครื่องอื่น ตรวจสอบ firewall:"
echo "   sudo ufw allow ${HTTP_PORT}/tcp   # Ubuntu/Debian"
echo "   sudo firewall-cmd --add-port=${HTTP_PORT}/tcp --permanent && sudo firewall-cmd --reload  # RHEL/CentOS"
echo ""
