# Чеклист СБ (Converter) — форк

Краткий трекер; детали — в `docs/security-*.md` и служебке ИБ.

- [ ] **МЭ:** снаружи только 443 (и редирект 80); `ss`/firewall согласованы.
- [ ] **SSH:** доступ только с терминального сервера / allowlist.
- [x] **Docker networks:** `docker-compose.vps.yml` разделяет `converter_frontend`, `converter_backend`, `converter_db`; DB-контейнеры подключены только к `converter_db`, RabbitMQ/MinIO доступны из backend-сети, host Nginx остаётся вне Docker.
- [x] **Approved deploy:** unattended `git reset --hard` autodeploy deprecated; ручной сценарий — `deploy/vps/manual-approved-deploy.sh.example` с `EXPECTED_COMMIT`, approval marker, backup и `docker compose --env-file deploy/vps/.env -f docker-compose.vps.yml up -d --build`.
- [ ] **GitOps:** `docker-compose.vps.yml` и `deploy/vps/.env.example` в репо; секреты только в `.env` на сервере.
- [x] **Server inventory:** `docs/security-asset-register.md` фиксирует `zvezda`, `155.212.160.162`, `converter.acom-offer-desk.ru`, purpose `Converter VPS runtime`.
- [ ] **Keycloak:** prod compose включает `KC_HOSTNAME_STRICT=true`; 2FA и prod `redirectUris` / `webOrigins` описаны в `infra/keycloak/README-SB.md`, live realm менять через Admin API/Console.
- [ ] **JWT:** в проде задан `KEYCLOAK_JWT_AUDIENCE`; см. `docs/security-api-hardening.md`.
- [x] **OpenAPI / Swagger:** prod compose задаёт `OPENAPI_PUBLIC_ENABLED=0`; анонимные бизнес-эндпоинты ещё проверить отдельно.
- [ ] **Образы:** `latest` убран из prod compose; effective config проверяется в CI; digest resolve/SBOM запускать через `scripts/security-sbom-scan.sh` и `docker compose config --resolve-image-digests` при доступной сети registry.
- [ ] **Контейнеры:** процесс не root (`USER` в Dockerfile; проверка в CI); MinIO запускается как `65532:65532`, поэтому volume `converter_minio_data` должен быть заранее мигрирован на владельца `65532:65532`.
- [ ] **БД/SZI:** GitOps-основа для Converter Postgres TLS добавлена: opt-in `CONVERTER_POSTGRES_TLS_ENABLED`, runtime-only cert generator `deploy/vps/generate-postgres-tls.sh`, compose mounts для `keycloak_db`/`nsi_db`/`documents_db`; включать только после backup по `docs/security-db-encryption.md`. Stage 1 = server TLS + `sslmode=require`; Stage 2 = `verify-full`/Keycloak `verify-server`.

## Live verification — Keycloak 2FA

- [x] **2026-05-06:** в realm `uom` для пользователя с ролью `operator` без фиксации секретов включён required action `CONFIGURE_TOTP`; ручная проверка QR/OTP на `https://converter.acom-offer-desk.ru/` прошла успешно.

## Pending / live notes

- [ ] На VPS после pull текущего commit запустить `docker compose --env-file deploy/vps/.env -f docker-compose.vps.yml config` и сверить, что активный compose — именно `docker-compose.vps.yml`, а не dev `docker-compose.yml`.
- [ ] Перед первым non-root MinIO запуском подтвердить ownership volume `converter_minio_data` = `65532:65532`; уже существующий live volume менять только после backup.
- [ ] При live deploy не трогать внешний `order_database` / порт `5432`; Converter использует только свои compose Postgres volumes и loopback-порты `18080/18001/18002/18003`.

Карточки Kaiten и внешний свод требований — по внутренней служебке ИБ.
