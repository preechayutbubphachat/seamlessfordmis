#!/usr/bin/env sh
set -eu
cd "$(dirname "$0")/.."
docker load -i images/postgres-16.tar
docker load -i images/nginx-alpine.tar
docker load -i images/seamlessfordmis-backend.tar
docker load -i images/seamlessfordmis-frontend.tar
echo "Images loaded."
