# Чеклист СБ (Converter) — форк

Краткий трекер; детали — в `docs/security-*.md` и служебке ИБ.

- [ ] **МЭ:** снаружи только 443 (и редирект 80); `ss`/firewall согласованы.
- [ ] **SSH:** доступ только с терминального сервера / allowlist.
- [ ] **GitOps:** `docker-compose.vps.yml` и `deploy/vps/.env.example` в репо; секреты только в `.env` на сервере.
- [ ] **Keycloak:** prod compose включает `KC_HOSTNAME_STRICT=true`; 2FA и prod `redirectUris` / `webOrigins` описаны в `infra/keycloak/README-SB.md`, live realm менять через Admin API/Console.
- [ ] **JWT:** в проде задан `KEYCLOAK_JWT_AUDIENCE`; см. `docs/security-api-hardening.md`.
- [x] **OpenAPI / Swagger:** prod compose задаёт `OPENAPI_PUBLIC_ENABLED=0`; анонимные бизнес-эндпоинты ещё проверить отдельно.
- [ ] **Образы:** `latest` убран из prod compose; effective config проверяется в CI; digest resolve/SBOM запускать через `scripts/security-sbom-scan.sh` и `docker compose config --resolve-image-digests` при доступной сети registry.
- [ ] **Контейнеры:** процесс не root (`USER` в Dockerfile; проверка в CI); MinIO запускается как `65532:65532`, поэтому volume `converter_minio_data` должен быть заранее мигрирован на владельца `65532:65532`.
- [ ] **БД/SZI:** GitOps-основа для Converter Postgres TLS добавлена: opt-in `CONVERTER_POSTGRES_TLS_ENABLED`, runtime-only cert generator `deploy/vps/generate-postgres-tls.sh`, compose mounts для `keycloak_db`/`nsi_db`/`documents_db`; включать только после backup по `docs/security-db-encryption.md`. Stage 1 = server TLS + `sslmode=require`; Stage 2 = `verify-full`/Keycloak `verify-server`.

## Live verification — Keycloak 2FA

- [x] **2026-05-06:** в realm `uom` для пользователя с ролью `operator` без фиксации секретов включён required action `CONFIGURE_TOTP`; ручная проверка QR/OTP на `https://converter.acom-offer-desk.ru/` прошла успешно.

Карточки Kaiten и внешний свод требований — по внутренней служебке ИБ.
