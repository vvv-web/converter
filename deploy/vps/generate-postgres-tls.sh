#!/usr/bin/env sh
set -eu

# Генерирует runtime-only TLS-материалы PostgreSQL для DB-сервисов Converter.
# Не коммитить каталог вывода: он исключён через .gitignore.

BASE_DIR="${1:-deploy/vps/postgres-tls}"
DAYS_CA="${DAYS_CA:-3650}"
DAYS_SERVER="${DAYS_SERVER:-825}"
POSTGRES_UID="${POSTGRES_UID:-70}"
POSTGRES_GID="${POSTGRES_GID:-70}"

if ! command -v openssl >/dev/null 2>&1; then
  echo "openssl is required" >&2
  exit 1
fi

umask 077
mkdir -p "$BASE_DIR"

CA_KEY="$BASE_DIR/root.key"
CA_CRT="$BASE_DIR/root.crt"

if [ -e "$CA_KEY" ] || [ -e "$CA_CRT" ]; then
  echo "Refusing to overwrite existing CA files in $BASE_DIR" >&2
  echo "Move the old CA files aside before rotating certificates." >&2
  exit 1
fi

openssl req -new -x509 -nodes -days "$DAYS_CA" \
  -newkey rsa:4096 \
  -keyout "$CA_KEY" \
  -out "$CA_CRT" \
  -subj "/CN=converter-postgres-internal-ca" \
  -addext "basicConstraints=critical,CA:TRUE" \
  -addext "keyUsage=critical,keyCertSign,cRLSign" \
  -addext "subjectKeyIdentifier=hash"

for svc in keycloak_db nsi_db documents_db; do
  svc_dir="$BASE_DIR/$svc"
  mkdir -p "$svc_dir"

  openssl req -new -nodes \
    -newkey rsa:2048 \
    -keyout "$svc_dir/server.key" \
    -out "$svc_dir/server.csr" \
    -subj "/CN=$svc" \
    -addext "subjectAltName=DNS:$svc"

  cat >"$svc_dir/server.ext" <<EOF
basicConstraints=CA:FALSE
keyUsage=digitalSignature,keyEncipherment
extendedKeyUsage=serverAuth
subjectAltName=DNS:$svc
EOF

  openssl x509 -req -days "$DAYS_SERVER" \
    -in "$svc_dir/server.csr" \
    -CA "$CA_CRT" \
    -CAkey "$CA_KEY" \
    -CAcreateserial \
    -out "$svc_dir/server.crt" \
    -extfile "$svc_dir/server.ext"

  cp "$CA_CRT" "$svc_dir/root.crt"
  chmod 0600 "$svc_dir/server.key"
  chmod 0644 "$svc_dir/server.crt" "$svc_dir/root.crt"
  rm -f "$svc_dir/server.csr" "$svc_dir/server.ext"
done

chmod 0600 "$CA_KEY"
chmod 0644 "$CA_CRT"

if [ "$(id -u)" -eq 0 ]; then
  chown -R "$POSTGRES_UID:$POSTGRES_GID" "$BASE_DIR/keycloak_db" "$BASE_DIR/nsi_db" "$BASE_DIR/documents_db"
  chown root:root "$CA_KEY" "$CA_CRT" 2>/dev/null || true
else
  echo "Generated files as $(id -un). On the VPS, run this before enabling TLS:"
  echo "  sudo chown -R $POSTGRES_UID:$POSTGRES_GID $BASE_DIR/keycloak_db $BASE_DIR/nsi_db $BASE_DIR/documents_db"
fi

echo "Generated PostgreSQL TLS files under $BASE_DIR"
echo "Keep $CA_KEY offline or root-only; clients only need $CA_CRT."
