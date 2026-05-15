# Чеклист СБ (Converter) — форк

**Ревизия:** 2026-05-07 — синхронизировано с `docker-compose.vps.yml`, устранёнными замечаниями аудита **docker-compose** (в т.ч. Чумаков / внутренний перечень) и поставкой **PyJWT 2.12.0** в сервисах приложения.

Краткий трекер; детали — в `docs/security-*.md`, `deploy/vps/*`, `infra/keycloak/README-SB.md`.

---

## Закрыто в репозитории и на тестовом VPS (технический контур приложения)

- [x] **Публикация портов только на loopback:** в `docker-compose.vps.yml` все `ports:` с префиксом `127.0.0.1:` (Keycloak **18080**, NSI **18001**, documents **18002**, conversion **18003**, RabbitMQ **25672/25673**, MinIO **29000/29001**). Проверка: `ss -tlnp` на хосте, сопоставление с compose; снаружи — **Nginx :443**.
- [x] **Keycloak в продуктивном режиме:** `command` содержит **`start`**, не `start-dev`; `KC_HOSTNAME_STRICT=true` в VPS-схеме.
- [x] **Redis в стеке не используется** — замечания про неаутентифицированный Redis к **Converter** не применимы; очередь — **RabbitMQ**.
- [x] **RabbitMQ без guest/guest:** `RABBITMQ_DEFAULT_USER` / `RABBITMQ_DEFAULT_PASS` в compose и **`deploy/vps/.env.example`**; `CELERY_BROKER_URL` в **documents** / **documents_worker** через эти переменные. На VPS значения только в **`deploy/vps/.env`** (не в git).
- [x] **MinIO не от root:** `user: "65532:65532"` в `docker-compose.vps.yml`. Перед переводом существующего **volume** данных на нового владельца — только после **бэкапа** (см. pending ниже).
- [x] **Сегментация сетей Docker:** `converter_frontend`, `converter_backend`, `converter_db`; **`converter_db` — `internal: true`**.
- [x] **Образы в `docker-compose.vps.yml` (VPS):** внешние образы с **тегом + `@sha256:`** (RabbitMQ, MinIO, Keycloak, Postgres в `docker-compose.vps.yml`). Dev `docker-compose.yml`: критичные сервисы выровнены по digests с VPS; **Postgres** в dev может оставаться `postgres:16-alpine` без digest (локальная разработка).
- [x] **OpenAPI / Swagger в прод-схеме:** `OPENAPI_PUBLIC_ENABLED=0` по умолчанию в сервисах; анонимные бизнес-эндпоинты — отдельная проверка по `docs/security-api-hardening.md`.
- [x] **PyJWT (замечание СБ):** **`PyJWT[crypto]==2.12.0`** в **nsi / documents / conversion** `requirements.txt`; образы пересобираются с этой версией (носитель: `02_obrazy/*.tar`, `HESH-GIT-KOMITA.txt`).
- [x] **Выкат на VPS (требование СБ):** автодеплой **не используется**; развёртывание на текущем VPS — **только вручную по согласованной процедуре**; **единственная ветка для выката на VPS — `test`** (см. `deploy/vps/RUNBOOK.md`, `manual-approved-deploy.sh.example`).
- [x] **Approved deploy:** явное подтверждение выката, без «тихого» `git reset --hard` — `deploy/vps/manual-approved-deploy.sh.example` (см. `deploy/vps/README.md`).
- [x] **Документация под аудит:** `deploy/vps/AUTODEPLOY-SB-NOTES.md` (история/запрет автодеплоя), `SECRET-STORAGE-NOTES.md`, `docs/security-sb-organizational-controls.md`, `docs/security-sb-mtls-scope.md`, `docs/security-sb-delivery-pack.md`, проверка compose в CI (`.github/scripts/check_vps_compose_security.py` и др. по факту в репо).
- [x] **Реестр активов (шаблон):** `docs/security-asset-register.md` (хост, FQDN, назначение).
- [x] **2FA Keycloak (подтверждение на контуре):** required action **CONFIGURE_TOTP** для контрольной роли; см. раздел «Live verification» ниже и `infra/keycloak/README-SB.md`.

---

## На стороне ИБ / эксплуатации ЦОД (вне git-репозитория)

- [ ] **МЭ:** снаружи только **443** (и при необходимости редирект **80**); правила **firewall** / **ss** согласованы с ИБ.
- [ ] **SSH / административный доступ:** политика организации (allowlist, журналирование, разделение ролей) — **не конфигурируется** файлом **Converter**.
- [ ] **KEYCLOAK_JWT_AUDIENCE:** в проде задать непустое значение при требовании ИБ; см. `docs/security-api-hardening.md` и комментарии в compose.
- [ ] **GitOps-секреты:** `deploy/vps/.env` на сервере, права и резервное копирование по регламенту; в репо только `.env.example` без секретов.
- [ ] **БД / TLS:** opt-in `CONVERTER_POSTGRES_TLS_ENABLED`, скрипты и mount в `deploy/vps/` — включать только после backup; `docs/security-db-encryption.md`.
- [ ] **Полный east-west mTLS** между всеми микросервисами — вне scope текущего релиза; `docs/security-sb-mtls-scope.md`.
- [ ] **SBOM / сканирование образов:** периодически `scripts/security-sbom-scan.sh`, `docker compose config --resolve-image-digests` при доступе к registry.

---

## Live verification — Keycloak 2FA

- [x] **2026-05-06:** в realm `uom` для пользователя с ролью `operator` без фиксации секретов включён required action `CONFIGURE_TOTP`; ручная проверка QR/OTP на `https://converter.acom-offer-desk.ru/` прошла успешно.

---

## Pending / операционные напоминания

- [ ] После каждого значимого **pull** на VPS: `docker compose --env-file deploy/vps/.env -f docker-compose.vps.yml config` и убедиться, что активен **`docker-compose.vps.yml`**, не dev `docker-compose.yml`.
- [ ] Убедиться, что в **`deploy/vps/.env`** заданы **RABBITMQ_*** и прочие обязательные переменные (иначе `config` / `up` падают); секреты не светить в логах.
- [ ] Перед первым **non-root MinIO** на уже существующем **volume** данных — **бэкап** и смена владельца каталога данных на **65532:65532** (см. заметки в `AGENTS.md` / эксплуатацию).
- [ ] При live-деплое не затрагивать внешний **order_database** / чужой **5432**; **Converter** использует свои тома Postgres и перечисленные loopback-порты.

---

*Карточки Kaiten и внешний свод требований — по внутренней служебке ИБ.*
