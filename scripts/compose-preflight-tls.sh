#!/usr/bin/env bash
# Подготовка TLS-материалов для docker-compose.vps.yml (локально / CI). Секреты не создаёт.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

need() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "missing: $1" >&2
    exit 1
  fi
}

need openssl
need docker

if [ ! -f deploy/vps/postgres-tls/root.crt ]; then
  echo "== postgres TLS =="
  ./deploy/vps/generate-postgres-tls.sh
else
  echo "postgres TLS: OK"
fi

if [ ! -f deploy/vps/tls/rabbitmq/ca_certificate.pem ]; then
  echo "== rabbitmq mTLS =="
  ./deploy/vps/generate-rabbitmq-mtls.sh
else
  echo "rabbitmq TLS: OK"
fi

if [ ! -f deploy/vps/tls/minio/public.crt ]; then
  echo "== minio TLS =="
  ./deploy/vps/generate-minio-tls.sh
else
  echo "minio TLS: OK"
fi

echo "TLS preflight: done"
