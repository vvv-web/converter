#!/usr/bin/env sh
set -eu

# Runtime-only TLS for MinIO (internal HTTPS). Output is gitignored — run before first compose up.
BASE_DIR="${1:-deploy/vps/tls/minio}"
DAYS_CA="${DAYS_CA:-3650}"
DAYS_CERT="${DAYS_CERT:-825}"

if ! command -v openssl >/dev/null 2>&1; then
  echo "openssl is required" >&2
  exit 1
fi

umask 077
mkdir -p "$BASE_DIR/CAs"

CA_KEY="$BASE_DIR/CAs/ca.key"
CA_CRT="$BASE_DIR/CAs/ca.crt"
PRIV_KEY="$BASE_DIR/private.key"
PUB_CRT="$BASE_DIR/public.crt"
PUBLIC_CA="$BASE_DIR/CAs/public.crt"

if [ -e "$PRIV_KEY" ] && [ -e "$PUB_CRT" ] && [ -e "$PUBLIC_CA" ]; then
  echo "MinIO TLS already present under $BASE_DIR — skip"
  exit 0
fi

if [ -e "$CA_KEY" ] || [ -e "$CA_CRT" ]; then
  echo "Refusing to overwrite partial CA in $BASE_DIR" >&2
  exit 1
fi

openssl req -new -x509 -nodes -days "$DAYS_CA" \
  -newkey rsa:4096 \
  -keyout "$CA_KEY" \
  -out "$CA_CRT" \
  -subj "/CN=converter-minio-internal-ca" \
  -addext "basicConstraints=critical,CA:TRUE" \
  -addext "keyUsage=critical,keyCertSign,cRLSign"

openssl req -new -nodes -days "$DAYS_CERT" \
  -newkey rsa:4096 \
  -keyout "$PRIV_KEY" \
  -out "$BASE_DIR/server.csr" \
  -subj "/CN=minio"

openssl x509 -req -days "$DAYS_CERT" \
  -in "$BASE_DIR/server.csr" \
  -CA "$CA_CRT" \
  -CAkey "$CA_KEY" \
  -CAcreateserial \
  -out "$PUB_CRT" \
  -extfile /dev/stdin <<EOF
subjectAltName=DNS:minio,DNS:localhost,IP:127.0.0.1
extendedKeyUsage=serverAuth
EOF

cp "$CA_CRT" "$PUBLIC_CA"
rm -f "$BASE_DIR/server.csr" "$BASE_DIR/ca.srl"

chmod 0600 "$CA_KEY" "$PRIV_KEY"
chmod 0644 "$CA_CRT" "$PUB_CRT" "$PUBLIC_CA"

echo "Generated MinIO TLS under $BASE_DIR"
