#!/usr/bin/env sh
set -eu
cd "$(dirname "$0")/.."

if [ -f .env ]; then
  set -a
  # shellcheck disable=SC1091
  . ./.env
  set +a
fi

POSTGRES_USER="${POSTGRES_USER:-seamlessfordmis}"
POSTGRES_DB="${POSTGRES_DB:-seamlessfordmis}"
STAMP="$(date +%Y%m%d-%H%M%S)"
BACKUP_DIR="data/backups/$STAMP"
mkdir -p "$BACKUP_DIR"

echo "Backing up PostgreSQL to $BACKUP_DIR/database.sql"
docker compose exec -T db pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" > "$BACKUP_DIR/database.sql"

echo "Archiving Docker volumes to $BACKUP_DIR"
docker run --rm -v seamlessfordmis_source_data:/source_data:ro -v "$(pwd)/$BACKUP_DIR":/backup nginx:alpine tar -czf /backup/source_data.tar.gz -C / source_data
docker run --rm -v seamlessfordmis_uploads:/uploads:ro -v "$(pwd)/$BACKUP_DIR":/backup nginx:alpine tar -czf /backup/uploads.tar.gz -C / uploads
docker run --rm -v seamlessfordmis_reports:/reports:ro -v "$(pwd)/$BACKUP_DIR":/backup nginx:alpine tar -czf /backup/reports.tar.gz -C / reports
docker run --rm -v seamlessfordmis_logs:/logs:ro -v "$(pwd)/$BACKUP_DIR":/backup nginx:alpine tar -czf /backup/logs.tar.gz -C / logs

# สำรอง .env
if [ -f .env ]; then
  cp .env "$BACKUP_DIR/.env.bak"
  echo "Saved .env.bak to $BACKUP_DIR"
fi

echo "Backup completed: $BACKUP_DIR"
