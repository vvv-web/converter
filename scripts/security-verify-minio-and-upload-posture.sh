#!/usr/bin/env bash
# Проверка для СБ: MinIO non-root на VPS и отсутствие upload-эндпоинтов в compose.
# Без вывода секретов. Запуск: из корня репозитория на хосте с Docker.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.vps.yml}"
ENV_FILE="${ENV_FILE:-/etc/converter/.env}"
PROJECT="${COMPOSE_PROJECT_NAME:-converter}"

fail=0
ok() { printf '  OK  %s\n' "$*"; }
warn() { printf '  WARN %s\n' "$*"; }
bad() { printf '  FAIL %s\n' "$*"; fail=1; }

echo "== Converter security posture (MinIO + upload) =="
echo "compose: $COMPOSE_FILE"
echo

# --- Compose invariants ---
if [[ ! -f "$COMPOSE_FILE" ]]; then
  bad "missing $COMPOSE_FILE"
  exit 1
fi

if awk '/^  minio:/{f=1} f&&/user:/{print; exit}' "$COMPOSE_FILE" | grep -q '65532:65532'; then
  ok "$COMPOSE_FILE: minio user 65532:65532"
else
  bad "minio must run as user 65532:65532 in $COMPOSE_FILE"
fi

if grep -q 'presigned_put\|UploadFile\|multipart/form-data' services/documents/apps/documents_core/views.py 2>/dev/null; then
  bad "unexpected upload patterns in documents views"
else
  ok "documents views: no upload API patterns in grep scan"
fi

# --- Runtime (optional, needs running stack) ---
compose_cmd=(docker compose -f "$COMPOSE_FILE")
if [[ -f "$ENV_FILE" ]]; then
  compose_cmd+=(--env-file "$ENV_FILE")
fi

minio_c="${PROJECT}-minio-1"
docs_c="${PROJECT}-documents-1"

if docker ps --format '{{.Names}}' | grep -qx "$minio_c"; then
  echo
  echo "== Runtime: container users =="
  minio_uid="$(docker exec "$minio_c" id -u 2>/dev/null || true)"
  if [[ "$minio_uid" == "65532" ]]; then
    ok "minio container uid: 65532"
  else
    bad "minio container uid=$minio_uid (expected 65532)"
  fi
else
  warn "container $minio_c not running — skip runtime minio check"
fi

if docker ps --format '{{.Names}}' | grep -qx "$docs_c"; then
  docs_uid="$(docker exec "$docs_c" id -u 2>/dev/null || true)"
  if [[ "$docs_uid" == "65532" ]]; then
    ok "documents container uid: 65532"
  else
    bad "documents container uid=$docs_uid (expected 65532)"
  fi
else
  warn "container $docs_c not running — skip runtime documents check"
fi

echo
echo "== Note for SB =="
echo "  MINIO_ROOT_USER is S3 admin account name, not Linux root."
echo "  No user file upload endpoint — see docs/security-sb-file-upload-and-minio.md"
echo

if [[ "$fail" -ne 0 ]]; then
  echo "RESULT: FAIL"
  exit 1
fi
echo "RESULT: PASS"
exit 0
