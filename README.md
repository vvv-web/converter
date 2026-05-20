# Converter — ветка `sb-security-fixes` (контур Службы безопасности)

**Репозиторий:** [vvv-web/converter](https://github.com/vvv-web/converter)  
**Ветка:** `sb-security-fixes` — **только** hardening под требования ИБ. Это **не** ветка ежедневной разработки продукта (`test` / `main` канона — отдельно).

**Назначение приложения:** калькулятор накладных (НСИ, расчёт, генерация XLSX/PDF на сервере). Пользователь **не загружает** файлы в систему — см. [docs/security-sb-file-upload-and-minio.md](docs/security-sb-file-upload-and-minio.md).

---

## Единственный рабочий стек

| Что | Файл |
|-----|------|
| **VPS / аудит ИБ / прод** | [`docker-compose.vps.yml`](docker-compose.vps.yml) |
| Секреты на сервере | `/etc/converter/.env` (chmod `600`, **не в git**) |
| Шаблон переменных | [`deploy/vps/.env.example`](deploy/vps/.env.example) |
| Выкат | [`deploy/vps/README.md`](deploy/vps/README.md), `manual-approved-deploy.sh.example` |

Файл [`docker-compose.yml`](docker-compose.yml) — только `include` того же манифеста (для CI). **Отдельного «dev compose» в ветке нет.**

---

## С чего начать проверяющему ИБ

1. [docs/SECURITY-SB-AUDIT-SCOPE.md](docs/SECURITY-SB-AUDIT-SCOPE.md) — область аудита и ссылки.  
2. [docs/security-sb-checklist.md](docs/security-sb-checklist.md) — статус по пунктам (в т.ч. резолюции AUD).  
3. [docs/security-sb-requirements-mapping.md](docs/security-sb-requirements-mapping.md) — соответствие формулировкам ИБ (Чумаков / Булатов).  
4. На VPS после pull ветки:
   ```bash
   cd /opt/converter
   docker compose --env-file /etc/converter/.env -f docker-compose.vps.yml config
   python3 .github/scripts/check_vps_compose_security.py \
     <(docker compose --env-file /etc/converter/.env -f docker-compose.vps.yml config --format json) \
     deploy/vps/.env.example
   ./scripts/security-verify-minio-and-upload-posture.sh
   ```

---

## Технический контур (кратко)

- Порты сервисов на хосте — **только `127.0.0.1`** (наружу — **Nginx :443**).  
- Keycloak — **`start`**, не `start-dev`; аутентификация + 2FA (см. `infra/keycloak/README-SB.md`).  
- **Redis в стеке нет** — очередь Celery: **RabbitMQ** (TLS `5671`, без plaintext `5672`).  
- MinIO — **`user: 65532:65532`**; `MINIO_ROOT_USER` — логин S3-API, не Linux root.  
- Сети Docker: **`converter_frontend`**, **`converter_backend`**, **`converter_db`** (`internal: true`).  
- PostgreSQL — TLS (`CONVERTER_POSTGRES_TLS_ENABLED=on`).  
- Образы — pin + `@sha256` в `docker-compose.vps.yml`.

Организационные пункты (МЭ только 443, SSH через терминальный сервер, SBOM по регламенту ИБ) — [docs/security-sb-organizational-controls.md](docs/security-sb-organizational-controls.md).

---

## Документация ветки (только СБ)

| Документ | Тема |
|----------|------|
| [security-sb-checklist.md](docs/security-sb-checklist.md) | Чеклист |
| [security-sb-file-upload-and-minio.md](docs/security-sb-file-upload-and-minio.md) | MinIO, upload N/A |
| [security-ports.md](docs/security-ports.md) | Порты |
| [security-db-encryption.md](docs/security-db-encryption.md) | TLS БД |
| [security-api-hardening.md](docs/security-api-hardening.md) | API / OpenAPI |
| [security-sb-mtls-scope.md](docs/security-sb-mtls-scope.md) | Границы mTLS |
| [security-sb-delivery-pack.md](docs/security-sb-delivery-pack.md) | Поставка на носитель |
| [deploy/vps/AUTODEPLOY-SB-NOTES.md](deploy/vps/AUTODEPLOY-SB-NOTES.md) | Запрет автодеплоя |

Канон требований для всех проектов: [vvv-web/security-board-requirements](https://github.com/vvv-web/security-board-requirements).

---

## После приёмки СБ

Перенос в канон (`test` / upstream) — отдельный merge по согласованию с ИБ. До переноса **live VPS** и аудит = **`sb-security-fixes`** + `/etc/converter/.env`.
