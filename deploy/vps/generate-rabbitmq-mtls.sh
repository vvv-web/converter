#!/bin/sh
set -eu

BASE_DIR="${1:-deploy/vps/tls/rabbitmq}"
DAYS_CA="${DAYS_CA:-3650}"
DAYS_CERT="${DAYS_CERT:-825}"
RABBITMQ_UID="${RABBITMQ_UID:-999}"
RABBITMQ_GID="${RABBITMQ_GID:-999}"
APP_UID="${APP_UID:-65532}"
APP_GID="${APP_GID:-65532}"

if ! command -v openssl >/dev/null 2>&1; then
  echo "openssl is required" >&2
  exit 1
fi

umask 077
mkdir -p "$BASE_DIR"

CA_KEY="$BASE_DIR/ca_key.pem"
CA_CERT="$BASE_DIR/ca_certificate.pem"
SERVER_KEY="$BASE_DIR/server_key.pem"
SERVER_CERT="$BASE_DIR/server_certificate.pem"
CLIENT_KEY="$BASE_DIR/client_key.pem"
CLIENT_CERT="$BASE_DIR/client_certificate.pem"

if [ ! -f "$CA_KEY" ] || [ ! -f "$CA_CERT" ]; then
  openssl req -new -x509 -nodes -days "$DAYS_CA" \
    -newkey rsa:4096 \
    -keyout "$CA_KEY" \
    -out "$CA_CERT" \
    -subj "/CN=converter-rabbitmq-internal-ca"
fi

make_cert() {
  name="$1"
  common_name="$2"
  usage="$3"
  san="$4"
  key_path="$5"
  csr_path="$BASE_DIR/${name}.csr"
  cert_path="$BASE_DIR/${name}_certificate.pem"
  ext_path="$BASE_DIR/${name}.ext"

  openssl req -new -nodes \
    -newkey rsa:2048 \
    -keyout "$key_path" \
    -out "$csr_path" \
    -subj "/CN=${common_name}"

  cat >"$ext_path" <<EOF
basicConstraints=CA:FALSE
keyUsage=digitalSignature,keyEncipherment
extendedKeyUsage=${usage}
${san}
EOF

  openssl x509 -req -days "$DAYS_CERT" \
    -in "$csr_path" \
    -CA "$CA_CERT" \
    -CAkey "$CA_KEY" \
    -CAcreateserial \
    -out "$cert_path" \
    -extfile "$ext_path"

  rm -f "$csr_path" "$ext_path"
}

make_cert "server" "rabbitmq" "serverAuth" "subjectAltName=DNS:rabbitmq" "$SERVER_KEY"
make_cert "client" "documents-worker" "clientAuth" "" "$CLIENT_KEY"

cat >"$BASE_DIR/rabbitmq.conf" <<'EOF'
listeners.tcp = none
listeners.ssl.default = 5671
ssl_options.cacertfile = /etc/rabbitmq/tls/ca_certificate.pem
ssl_options.certfile = /etc/rabbitmq/tls/server_certificate.pem
ssl_options.keyfile = /etc/rabbitmq/tls/server_key.pem
ssl_options.verify = verify_peer
ssl_options.fail_if_no_peer_cert = true
EOF

chmod 0600 "$CA_KEY" "$SERVER_KEY" "$CLIENT_KEY"
chmod 0644 "$CA_CERT" "$SERVER_CERT" "$CLIENT_CERT" "$BASE_DIR/rabbitmq.conf"

if [ "$(id -u)" -eq 0 ]; then
  chown "$RABBITMQ_UID:$RABBITMQ_GID" "$SERVER_KEY" "$SERVER_CERT"
  chown "$APP_UID:$APP_GID" "$CLIENT_KEY" "$CLIENT_CERT"
fi

echo "Generated RabbitMQ mTLS assets under $BASE_DIR"
