#!/usr/bin/env sh
set -eu
cd "$(dirname "$0")/.."

RESTORE_DIR="${1:-}"
if [ -z "$RESTORE_DIR" ] || [ ! -f "$RESTORE_DIR/database.sql" ]; then
  echo "Usage: sh offline/restore.sh data/backups/YYYYMMDD-HHMMSS"
  exit 1
fi

echo "This will destructively restore the database from:"
echo "$RESTORE_DIR/database.sql"
printf "Type RESTORE to continue: "
read -r CONFIRM
[ "$CONFIRM" = "RESTORE" ] || {
  echo "Restore cancelled."
  exit 1
}

if [ -f .env ]; then
  set -a
  # shellcheck disable=SC1091
  . ./.env
  set +a
fi

POSTGRES_USER="${POSTGRES_USER:-seamlessfordmis}"
POSTGRES_DB="${POSTGRES_DB:-seamlessfordmis}"

docker compose up -d db
printf "DROP SCHEMA public CASCADE; CREATE SCHEMA public;" | docker compose exec -T db psql -U "$POSTGRES_USER" -d "$POSTGRES_DB"
docker compose exec -T db psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" < "$RESTORE_DIR/database.sql"

[ -f "$RESTORE_DIR/source_data.tar.gz" ] && docker run --rm -v seamlessfordmis_source_data:/source_data -v "$(pwd)/$RESTORE_DIR":/backup nginx:alpine sh -c "rm -rf /source_data/* && tar -xzf /backup/source_data.tar.gz -C /"
[ -f "$RESTORE_DIR/uploads.tar.gz" ] && docker run --rm -v seamlessfordmis_uploads:/uploads -v "$(pwd)/$RESTORE_DIR":/backup nginx:alpine sh -c "rm -rf /uploads/* && tar -xzf /backup/uploads.tar.gz -C /"
[ -f "$RESTORE_DIR/reports.tar.gz" ] && docker run --rm -v seamlessfordmis_reports:/reports -v "$(pwd)/$RESTORE_DIR":/backup nginx:alpine sh -c "rm -rf /reports/* && tar -xzf /backup/reports.tar.gz -C /"
[ -f "$RESTORE_DIR/logs.tar.gz" ] && docker run --rm -v seamlessfordmis_logs:/logs -v "$(pwd)/$RESTORE_DIR":/backup nginx:alpine sh -c "rm -rf /logs/* && tar -xzf /backup/logs.tar.gz -C /"

echo "Restore completed."
