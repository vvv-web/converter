# Чеклист СБ (Converter) — форк

**Канон формулировок требований (все проекты):** приватный репозиторий **[vvv-web/security-board-requirements](https://github.com/vvv-web/security-board-requirements)** — `docs/REQUIREMENTS.md`, `docs/CHECKLIST.md`. Этот файл — **только статус выполнения** для Converter и ссылки на `docs/security-*.md`, `deploy/vps/*`.

**Ревизия:** 2026-05-19 — добавлена фиксация по загрузке файлов (N/A) и MinIO; 2026-05-18 — security branch `sb-security-fixes` выровнена с целевым VPS SB-profile: plaintext AMQP отключён, внутренний TLS проверяется клиентами, PostgreSQL TLS включён по умолчанию.

Краткий трекер; детали — в `docs/security-*.md`, `deploy/vps/*`, `infra/keycloak/README-SB.md`.  
**Соответствие резолюциям ИБ (Чумаков / Булатов):** [`security-sb-requirements-mapping.md`](security-sb-requirements-mapping.md).

---

## Закрыто в репозитории и на тестовом VPS (технический контур приложения)

- [x] **Публикация портов только на loopback:** в `docker-compose.vps.yml` все `ports:` с префиксом `127.0.0.1:` (Keycloak **18080**, NSI **18001**, documents **18002**, conversion **18003**, RabbitMQ **25671/25673**, MinIO **29000/29001**). Проверка: `ss -tlnp` на хосте, сопоставление с compose; снаружи — **Nginx :443**.
- [x] **Keycloak в продуктивном режиме:** `command` содержит **`start`**, не `start-dev`; `KC_HOSTNAME_STRICT=true` в VPS-схеме.
- [x] **Redis в стеке не используется** — замечания про неаутентифицированный Redis к **Converter** не применимы; очередь — **RabbitMQ**.
- [x] **RabbitMQ без guest/guest:** `RABBITMQ_DEFAULT_USER` / `RABBITMQ_DEFAULT_PASS` в compose и **`deploy/vps/.env.example`**; `CELERY_BROKER_URL` в **documents** / **documents_worker** через эти переменные. На VPS значения только в **`/etc/converter/.env`** (не в git).
- [x] **RabbitMQ без plaintext `5672`:** в `docker-compose.vps.yml` публикуется только TLS listener `127.0.0.1:25671 -> 5671`; `listeners.tcp = none` в `deploy/vps/tls/rabbitmq/rabbitmq.conf`.
- [x] **RabbitMQ TLS verification включена реально:** broker настроен на `verify_peer` + `fail_if_no_peer_cert=true`, а `documents` / `documents_worker` проверяют CA и используют client certificate для `amqps`.
- [x] **MinIO не от root (Linux):** `user: "65532:65532"` в `docker-compose.vps.yml`; `MINIO_ROOT_USER` — **имя учётки S3-API**, не UID 0. Проверка: `scripts/security-verify-minio-and-upload-posture.sh`, `docs/security-sb-file-upload-and-minio.md` §5.
- [x] **Нет пользовательской загрузки файлов:** эндпоинта upload / `multipart` / `<input type="file">` нет; в MinIO только серверные XLSX/PDF после «Сгенерировать». Обоснование: **`docs/security-sb-file-upload-and-minio.md`**.
- [x] **Сегментация сетей Docker:** `converter_frontend`, `converter_backend`, `converter_db`; **`converter_db` — `internal: true`**.
- [x] **Образы в `docker-compose.vps.yml`:** внешние образы с **тегом + `@sha256:`** (RabbitMQ, MinIO, Keycloak, Postgres). Локально/CI — тот же файл (`docker-compose.yml` только `include`).
- [x] **OpenAPI / Swagger в прод-схеме:** `OPENAPI_PUBLIC_ENABLED=0` по умолчанию в сервисах; анонимные бизнес-эндпоинты — отдельная проверка по `docs/security-api-hardening.md`.
- [x] **PyJWT (замечание СБ):** **`PyJWT[crypto]==2.12.0`** в **nsi / documents / conversion** `requirements.txt`; образы пересобираются с этой версией (носитель: `02_obrazy/*.tar`, `HESH-GIT-KOMITA.txt`).
- [x] **Выкат на VPS (требование СБ):** автодеплой **не используется**; развёртывание на текущем VPS — **только вручную по согласованной процедуре**; до переноса hardening в канон источником правды для VPS является **`sb-security-fixes`**.
- [x] **Публикация на хосте vs внутри контейнера:** на хосте только `127.0.0.1:*`; `runserver 0.0.0.0:8000` и `npm run dev --host 0.0.0.0` — **внутри** сети Docker (не публикация на `0.0.0.0` хоста). Профиль `ui`/`frontend` — не периметр VPS.
- [ ] **Bind-mount `./services/*` на VPS:** в `docker-compose.vps.yml` есть монтирование исходников для `up --build`; при аудите «образ без исходников на диске» — отдельное согласование с ИБ (образы уже на носителе / `docker save`).
- [x] **Approved deploy:** явное подтверждение выката, без «тихого» `git reset --hard` — `deploy/vps/manual-approved-deploy.sh.example` (см. `deploy/vps/README.md`).
- [x] **Документация под аудит:** `deploy/vps/AUTODEPLOY-SB-NOTES.md` (история/запрет автодеплоя), `SECRET-STORAGE-NOTES.md`, `docs/security-sb-organizational-controls.md`, `docs/security-sb-mtls-scope.md`, `docs/security-sb-delivery-pack.md`, проверка compose в CI (`.github/scripts/check_vps_compose_security.py` и др. по факту в репо).
- [x] **Реестр активов (шаблон):** `docs/security-asset-register.md` (хост, FQDN, назначение).
- [x] **2FA Keycloak (подтверждение на контуре):** required action **CONFIGURE_TOTP** для контрольной роли; см. раздел «Live verification» ниже и `infra/keycloak/README-SB.md`.

---

## На стороне ИБ / эксплуатации ЦОД (вне git-репозитория)

- [ ] **МЭ:** снаружи только **443** (и при необходимости редирект **80**); правила **firewall** / **ss** согласованы с ИБ.
- [ ] **SSH / административный доступ:** политика организации (allowlist, журналирование, разделение ролей) — **не конфигурируется** файлом **Converter**.
- [ ] **KEYCLOAK_JWT_AUDIENCE:** в проде задать непустое значение при требовании ИБ; см. `docs/security-api-hardening.md` и комментарии в compose.
- [x] **GitOps-секреты:** runtime env вынесен в `/etc/converter/.env` на сервере, права `0600`; в репо только `.env.example` без секретов.
- [x] **БД / TLS:** security branch включает PostgreSQL TLS по умолчанию (`CONVERTER_POSTGRES_TLS_ENABLED=on`), Django использует `sslmode=verify-full`, Keycloak — `verify-server`; детали в `docs/security-db-encryption.md`.
- [ ] **Полный east-west mTLS** между всеми микросервисами — вне scope текущего релиза; `docs/security-sb-mtls-scope.md`.
- [ ] **SBOM / сканирование образов:** периодически `scripts/security-sbom-scan.sh`, `docker compose config --resolve-image-digests` при доступе к registry.

---

## Live verification — Keycloak 2FA

- [x] **2026-05-06:** в realm `uom` для пользователя с ролью `operator` без фиксации секретов включён required action `CONFIGURE_TOTP`; ручная проверка QR/OTP на `https://converter.acom-offer-desk.ru/` прошла успешно.

---

## Pending / операционные напоминания

- [x] После каждого значимого **pull** на VPS: `docker compose --env-file /etc/converter/.env -f docker-compose.vps.yml config` (отдельного dev-compose в ветке нет).
- [x] Убедиться, что в **`/etc/converter/.env`** заданы **RABBITMQ_***, broker/client TLS paths и прочие обязательные переменные (иначе `config` / `up` падают); секреты не светить в логах.
- [ ] Перед первым **non-root MinIO** на уже существующем **volume** данных — **бэкап** и смена владельца каталога данных на **65532:65532** (см. заметки в `AGENTS.md` / эксплуатацию).
- [ ] При live-деплое не затрагивать внешний **order_database** / чужой **5432**; **Converter** использует свои тома Postgres и перечисленные loopback-порты.

---

*Карточки Kaiten и внешний свод требований — по внутренней служебке ИБ.*
