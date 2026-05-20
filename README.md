# Converter

[![CI](https://github.com/vldsmelov/converter/actions/workflows/ci.yml/badge.svg)](https://github.com/vldsmelov/converter/actions/workflows/ci.yml)

**Назначение:** Converter — **калькулятор накладных** (конвертация единиц измерения по правилам НСИ). Пользователь **не загружает файлы**: нет API upload, нет поля `file` во фронтенде. В **MinIO** только Excel/PDF, **собранные сервером** после «Сгенерировать». Подсунуть чужой файл через веб **нельзя**. На production MinIO работает от UID **65532**, не от root ОС; **`MINIO_ROOT_USER`** — логин S3 в MinIO, **не** суперпользователь Linux. Обоснование и команды проверки: [docs/security-sb-file-upload-and-minio.md](docs/security-sb-file-upload-and-minio.md), скрипт `scripts/security-verify-minio-and-upload-posture.sh` на VPS. MinIO при необходимости можно убрать отдельным релизом — на **расчёт не влияет**.

Микросервисный прототип для:
- ведения НСИ (ЕИ, категории, номенклатура, упаковки, правила конвертации),
- расчета накладных,
- генерации итоговых XLSX/PDF,
- хранения файлов в MinIO,
- авторизации и ролей через Keycloak.

## Состав сервисов (ветка `sb-security-fixes`)

Единый манифест: **`docker-compose.vps.yml`** (TLS, loopback, non-root). На VPS — тот же файл; локально/CI — через `docker-compose.yml` (`include`).

| Сервис | Loopback (локально) | Назначение |
|--------|---------------------|------------|
| `keycloak` | `127.0.0.1:18080` | Auth (`/auth`) |
| `nsi` | `127.0.0.1:18001` | НСИ |
| `documents` | `127.0.0.1:18002` | Накладные |
| `conversion` | `127.0.0.1:18003` | Расчёт |
| `rabbitmq` | `127.0.0.1:25671` (TLS), mgmt `25673` | Celery |
| `minio` | `127.0.0.1:29000` / `29001` | Сгенерированные XLSX/PDF |

## Быстрый старт (локально, hardened как VPS)

1. `cp .env.example .env` — задать пароли (`MINIO_ROOT_USER`, `MINIO_ROOT_PASSWORD`, БД, …).
2. `./scripts/compose-preflight-tls.sh` — один раз сгенерировать TLS.
3. `docker compose --env-file .env up -d --build`
4. UI: `docker compose --env-file .env --profile ui up -d frontend` → `http://127.0.0.1:15173`
5. Keycloak Admin: `http://127.0.0.1:18080/auth`

## Health-check (с заголовком Host из `CONVERTER_ALLOWED_HOSTS`)

- NSI: `curl -fsS -H 'Host: localhost' http://127.0.0.1:18001/healthz`
- Documents: `curl -fsS -H 'Host: localhost' http://127.0.0.1:18002/healthz`
- Conversion: `http://127.0.0.1:18003/healthz`

**Аудит СБ:** только `docker-compose.vps.yml` + [`docs/SECURITY-SB-AUDIT-SCOPE.md`](docs/SECURITY-SB-AUDIT-SCOPE.md). Отдельного «dev compose» в ветке нет.

## Текущий функционал

### НСИ
- ЕИ:
  - список, создание, редактирование, удаление.
- Категории номенклатуры:
  - список, создание, редактирование, удаление.
- Номенклатура:
  - список, создание, редактирование.
- Упаковки:
  - список, создание, редактирование, удаление.
- Правила:
  - список в виде вкладок:
    - глобальные,
    - правила категорий,
    - правила номенклатуры;
  - создание, редактирование, удаление для каждого типа.

### Накладные
- Создание накладной.
- Проверка наличия правил конвертации при вводе строк.
- Расчет (`calculate`).
- Генерация итоговых файлов (`generate`).
- Скачивание XLSX/PDF.

## Изменения в экспорте файлов (актуально)
- В итоговых XLSX/PDF используется русский набор колонок:
  - `#`, `Товар`, `Кол-во`, `ЕИ (в документе)`, `Оприходование`, `Статус строки`.
- В колонке `Товар` записывается **название номенклатуры**, а не `item_id`.
- Для имени товара используется:
  1. `line.context.item_name` (если передан),
  2. fallback-запрос в NSI по `item_id`,
  3. резервный вариант `item_id=...`.
- PDF-генерация переведена на Unicode-шрифт `DejaVuSans` (в Docker-образ `documents` добавлена установка `fonts-dejavu-core`), чтобы корректно печаталась кириллица.

## Роли Keycloak (основные)
- NSI: `nsi.uom.*`, `nsi.item.*`, `nsi.package.*`, `nsi.rule.*`
- Conversion: `conversion.convert`, `conversion.ping`
- Documents: `documents.invoice.read`, `documents.invoice.write`, `documents.invoice.calculate`, `documents.invoice.generate`

## Полезные команды
- Полный перезапуск:
  - `docker compose down -v --remove-orphans`
  - `docker compose up -d --build`
- Пересобрать/перезапустить документы:
  - `docker compose up -d --build documents documents_worker`
- Сборка frontend:
  - `docker run --rm -v ${PWD}:/repo -w /repo/frontend node:20-alpine sh -lc "npm ci && npm run build"`
- E2E smoke:
  - `docker compose --profile tools run --rm e2e pytest -q tests/test_invoice_flow.py`
  - `docker compose --profile tools run --rm e2e pytest -q tests/test_end_to_end.py`

## Документация
- Операционный runbook: [docs/RUNBOOK.md](docs/RUNBOOK.md)
- Frontend заметки: [frontend/README.md](frontend/README.md)
- СБ: загрузка файлов и MinIO — [docs/security-sb-file-upload-and-minio.md](docs/security-sb-file-upload-and-minio.md)
- СБ: чеклист — [docs/security-sb-checklist.md](docs/security-sb-checklist.md)

## Admin reset (test mode)
- Realm role: `system.admin`
- Admin user is `administrator`; password is provisioned from env during seed/bootstrap and must not be stored in git.
- Reset endpoints (POST, admin only):
  - NSI: `/api/v1/admin/reset-defaults/`
  - Documents: `/api/v1/admin/reset-defaults/`
- Frontend: admin sees a reset icon button in the header.

## Администрирование пользователей и ролей
- В UI доступна страница `/admin/console` (видна только с ролью `system.admin`).
- Администратор может:
  - создавать пользователей,
  - создавать/редактировать роли и наборы прав пользователей,
  - назначать роль-пакеты (`bundle.*`) на основании permissions.
- Backend API (NSI, только `system.admin`):
  - `GET/POST /api/v1/admin/iam/roles/`
  - `GET/POST /api/v1/admin/iam/users/`
  - `PUT /api/v1/admin/iam/users/{user_id}/roles/`

## Поля по умолчанию
- Администратор может создавать системные поля по умолчанию:
  - `GET/POST /api/v1/admin/default-fields/` (admin only)
  - `GET /api/v1/default-fields/` (read для всех форм NSI)
- Эти поля доступны в интерфейсе, но не могут быть изменены/удалены через обычные API.
- При общем сбросе (`/api/v1/admin/reset-defaults/`) системные поля сохраняются.

## Quality Gate (CI)
- Frontend:
  - `npm run lint:strict`
  - `npm run build`
- Backend:
  - `python -m compileall services`
  - `ruff check services/nsi/apps services/nsi/nsi_service services/documents/apps services/documents/documents_service services/conversion/app`
  - NSI: `python manage.py check` and `python manage.py makemigrations --check --dry-run`
  - Documents: `python manage.py check` and `python manage.py makemigrations --check --dry-run`
- E2E:
  - `pytest -q --collect-only services/e2e/tests`

Local smoke (Docker):
```bash
docker run --rm -v ${PWD}:/repo -w /repo/frontend node:20-alpine sh -lc "npm ci && npm run lint:strict && npm run build"
docker compose run --rm nsi python manage.py check
docker compose run --rm nsi python manage.py makemigrations --check --dry-run
docker compose run --rm documents python manage.py check
docker compose run --rm documents python manage.py makemigrations --check --dry-run
```

## Обновления по требованиям Службы Безопасности (СБ) - Май 2026

Ветка **`sb-security-fixes`** — **отдельная ветка под СБ** (форк `vvv-web/converter`): источник правды для hardened VPS, пока изменения не перенесены в канон `test`. Live на VPS = эта ветка + `/etc/converter/.env`.

**Для аудита ИБ:** **[`docker-compose.vps.yml`](docker-compose.vps.yml)** (и [`docs/SECURITY-SB-AUDIT-SCOPE.md`](docs/SECURITY-SB-AUDIT-SCOPE.md)). [`docker-compose.yml`](docker-compose.yml) — тот же манифест через `include`, не отдельный dev-стек.

В рамках приведения проекта в соответствие с требованиями ИБ для VPS-профиля зафиксированы следующие требования:

1. **Изоляция сервисов:** Сервисы (RabbitMQ, MinIO, Keycloak) убраны с публичных интерфейсов и теперь слушают только `127.0.0.1`. Наружу смотрит только Nginx.
2. **Режим Keycloak:** Keycloak переведен из dev-режима в production (`start` вместо `start-dev`).
3. **Запуск без root:** На VPS (`docker-compose.vps.yml`) приложения и **MinIO** — `user: "65532:65532"`. Переменная **`MINIO_ROOT_USER`** — имя учётки S3-API, не Linux root.
4. **Разделение сетей:** Контейнеры разнесены по изолированным сетям (`converter_frontend`, `converter_backend`, `converter_db`).
5. **Фиксация версий:** Использование `latest` тегов заменено на конкретные версии с привязкой к `sha256` хэшам образов.
6. **Отключение автодеплоя:** Автоматический деплой из GitHub на VPS отключен.
7. **Шифрование БД:** PostgreSQL TLS включён по умолчанию; Django использует `sslmode=verify-full`, Keycloak — `verify-server`.
8. **Безопасное хранение секретов:** Runtime env вынесен из checkout в `/etc/converter/.env` (права `0600`).
9. **RabbitMQ только по TLS:** plaintext AMQP `5672` отключён; используется только `5671` с peer verification и client certificates для `documents` / `documents_worker`.
10. **MinIO TLS без `cert_check=False`:** `documents` / `documents_worker` проверяют внутренний сертификат MinIO через локальную CA.
11. **Без plaintext-credentials в git:** hardcoded пароли/секреты убраны из compose/env examples и realm export; bootstrap-пароли пользователей и `documents-service` client secret задаются только через env и выставляются seed/bootstrap-процедурой.
12. **Нет пользовательской загрузки файлов:** эндпоинта upload / `multipart` / `<input type="file">` нет; в MinIO только серверные XLSX/PDF. Документ для СЗ: [docs/security-sb-file-upload-and-minio.md](docs/security-sb-file-upload-and-minio.md).

**Ожидает завершения:**
* **Настройка сетевого экрана (UFW):** Порты 443 и 22 пока открыты глобально. Мы ожидаем выделения IP-адреса терминального сервера и списка IP корпоративного контура от инфраструктурной команды. Как только данные будут получены, доступ будет строго ограничен этими адресами.
