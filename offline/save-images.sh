#!/usr/bin/env sh
set -eu
cd "$(dirname "$0")/.."
mkdir -p images
docker pull postgres:16
docker pull nginx:alpine
docker compose build
docker save -o images/seamlessfordmis-backend.tar seamlessfordmis-backend:latest
docker save -o images/seamlessfordmis-frontend.tar seamlessfordmis-frontend:latest
docker save -o images/postgres-16.tar postgres:16
docker save -o images/nginx-alpine.tar nginx:alpine
echo "Images saved to images/"
