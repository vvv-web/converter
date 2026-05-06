# Шифрование данных БД (СБ)

Этот документ относится только к БД Converter: `keycloak_db`, `nsi_db`, `documents_db`.
`order_database` и публичный порт `5432` не входят в scope.

## Модель внедрения

В репозитории подготовлена безопасная GitOps-основа, но TLS включается на VPS вручную только после бэкапа volume:

1. `deploy/vps/generate-postgres-tls.sh` генерирует runtime-only CA и server-сертификаты для `keycloak_db`, `nsi_db`, `documents_db`.
2. `docker-compose.yml` и `docker-compose.vps.yml` монтируют `deploy/vps/postgres-tls/*` read-only и передают PostgreSQL параметры `ssl`, `ssl_cert_file`, `ssl_key_file`.
3. По умолчанию `CONVERTER_POSTGRES_TLS_ENABLED=off`, поэтому deploy без сертификатов не должен менять поведение БД.
4. Stage 1 включает server-side TLS и `sslmode=require` для Django-сервисов. Это шифрует трафик, но не проверяет имя сервера.
5. Stage 2 переводит клиенты на проверку CA/имени: `verify-full` для libpq/Django и `verify-server` для Keycloak после согласования lifecycle CA.

## Официальная опора

PostgreSQL 16, server-side TLS: <https://www.postgresql.org/docs/16/ssl-tcp.html>

> The PostgreSQL server can be started with support for encrypted connections using TLS protocols enabled by setting the parameter `ssl` to `on` in `postgresql.conf`. To start in SSL mode, files containing the server certificate and private key must exist.

PostgreSQL 16, libpq `sslmode`: <https://www.postgresql.org/docs/16/libpq-ssl.html>

> `require` means encrypted traffic without MITM protection; `verify-full` verifies that the server is trusted and that it is the host specified by the client. The PostgreSQL docs recommend `verify-full` in most security-sensitive environments.

Keycloak DB TLS options: <https://www.keycloak.org/server/db> and <https://www.keycloak.org/server/all-config>

> Keycloak recommends configuring PostgreSQL TLS on the server first and then using `--db-tls-mode=verify-server --db-tls-trust-store-file=/path/to/certificate`. The env equivalents are `KC_DB_TLS_MODE` and `KC_DB_TLS_TRUST_STORE_FILE`.

## Stage 0: inventory and backup

Run on the VPS in `/opt/converter`. Do not print `.env` values.

```bash
cd /opt/converter
docker compose -f docker-compose.yml ps keycloak_db nsi_db documents_db
docker volume inspect converter_keycloak_db converter_nsi_db converter_documents_db --format '{{ .Name }} -> {{ .Mountpoint }}'
```

Create dumps before changing TLS. Use only the three Converter DB containers:

```bash
cd /opt/converter
backup_dir="backups/postgres-tls-$(date +%Y%m%d-%H%M%S)"
mkdir -p "$backup_dir"

for svc in keycloak_db nsi_db documents_db; do
  echo "===== backup $svc ====="
  docker compose -f docker-compose.yml exec -T "$svc" sh -lc \
    'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc' \
    > "$backup_dir/$svc.dump"
  sha256sum "$backup_dir/$svc.dump" > "$backup_dir/$svc.dump.sha256"
done

ls -lh "$backup_dir"
```

Expected: three non-empty `.dump` files and three `.sha256` files.

## Stage 1: generate certificates

Run on the VPS from `/opt/converter`:

```bash
cd /opt/converter
sudo sh deploy/vps/generate-postgres-tls.sh
sudo chown -R 70:70 deploy/vps/postgres-tls/keycloak_db deploy/vps/postgres-tls/nsi_db deploy/vps/postgres-tls/documents_db
sudo chmod 0600 deploy/vps/postgres-tls/*/server.key
sudo chmod 0644 deploy/vps/postgres-tls/*/server.crt deploy/vps/postgres-tls/*/root.crt deploy/vps/postgres-tls/root.crt
sudo chmod 0600 deploy/vps/postgres-tls/root.key
```

Expected files:

```bash
find deploy/vps/postgres-tls -maxdepth 2 -type f -printf '%M %u:%g %p\n' | sort
```

`server.key` must not be readable by world/group. The CA private key `root.key` is sensitive; keep it root-only and move it offline if SB requires offline CA storage.

## Stage 2: enable server-side TLS

Edit `deploy/vps/.env` on the VPS, without pasting secrets into chat:

```text
CONVERTER_POSTGRES_TLS_ENABLED=on
NSI_DATABASE_URL=postgres://nsi:nsi@nsi_db:5432/nsi?sslmode=require
DOCUMENTS_DATABASE_URL=postgres://documents:documents@documents_db:5432/documents?sslmode=require
KC_DB_TLS_MODE=verify-server
KC_DB_TLS_TRUST_STORE_FILE=/etc/postgresql/tls/root.crt
```

Keycloak note: this repo wires the official `KC_DB_TLS_MODE` / `KC_DB_TLS_TRUST_STORE_FILE` env names, but Keycloak should be restarted only after the `root.crt` mount exists. If Keycloak rejects the TLS option on the live image, rollback Keycloak first and leave `keycloak_db` server-side TLS enabled until the exact image behavior is verified.

Deploy one DB at a time, then clients:

```bash
cd /opt/converter
docker compose -f docker-compose.yml up -d keycloak_db nsi_db documents_db
docker compose -f docker-compose.yml up -d keycloak nsi documents documents_worker
```

## Verification

Server-side PostgreSQL TLS:

```bash
cd /opt/converter
for svc in keycloak_db nsi_db documents_db; do
  echo "===== $svc ====="
  docker compose -f docker-compose.yml exec -T "$svc" sh -lc \
    'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -X -c "SHOW ssl;" -c "SHOW ssl_cert_file;" -c "SHOW ssl_key_file;"'
done
```

Expected: `ssl` is `on`, cert path is `/etc/postgresql/tls/server.crt`, key path is `/etc/postgresql/tls/server.key`.

Client-side encrypted sessions:

```bash
cd /opt/converter
for svc in nsi_db documents_db keycloak_db; do
  echo "===== $svc ====="
  docker compose -f docker-compose.yml exec -T "$svc" sh -lc \
    'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -X -c "SELECT usename, ssl, version FROM pg_stat_ssl JOIN pg_stat_activity USING (pid) WHERE usename = current_user;"'
done
```

Expected after clients reconnect: rows for active application users show `ssl = t`.

Application smoke:

```bash
curl -vkI https://converter.acom-offer-desk.ru/
curl -vkI https://converter.acom-offer-desk.ru/auth/realms/uom/.well-known/openid-configuration
```

Expected: Converter returns HTTP response, OIDC discovery returns `200`.

## Rollback

Disable client TLS first:

```bash
cd /opt/converter
sudo cp deploy/vps/.env deploy/vps/.env.before-db-tls-rollback.$(date +%Y%m%d-%H%M%S)
sudo sed -i '/^CONVERTER_POSTGRES_TLS_ENABLED=/d;/^KC_DB_TLS_MODE=/d;/^KC_DB_TLS_TRUST_STORE_FILE=/d' deploy/vps/.env
sudo sed -i 's/[?&]sslmode=require//g' deploy/vps/.env
docker compose -f docker-compose.yml up -d keycloak nsi documents documents_worker
```

If a PostgreSQL container fails to start because of certificate permissions, keep data volumes intact and start with TLS disabled:

```bash
cd /opt/converter
CONVERTER_POSTGRES_TLS_ENABLED=off docker compose -f docker-compose.yml up -d keycloak_db nsi_db documents_db
```

Do not remove DB volumes during rollback.

## Upgrade to `verify-full`

After SB accepts CA lifecycle and cert rotation:

1. Keep SANs equal to Docker service names: `keycloak_db`, `nsi_db`, `documents_db`.
2. Mount `deploy/vps/postgres-tls/root.crt` into Django containers.
3. Change URLs to include `sslmode=verify-full&sslrootcert=/etc/postgresql/tls/root.crt`.
4. Keep Keycloak on `KC_DB_TLS_MODE=verify-server` with `KC_DB_TLS_TRUST_STORE_FILE=/etc/postgresql/tls/root.crt`.

## At-rest

At-rest encryption remains a separate host/SB decision: LUKS, encrypted backups, or a mandated SZI agent. Record the chosen model and rollback procedure here; never commit keys or private certificates.
