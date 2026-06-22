#!/usr/bin/env sh
set -eu
cd "$(dirname "$0")/.."
docker compose logs --tail=200 -f db backend frontend nginx
