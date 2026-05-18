# Converter

[![CI](https://github.com/vldsmelov/converter/actions/workflows/ci.yml/badge.svg)](https://github.com/vldsmelov/converter/actions/workflows/ci.yml)
Микросервисный прототип для:
- ведения НСИ (ЕИ, категории, номенклатура, упаковки, правила конвертации),
- расчета накладных,
- генерации итоговых XLSX/PDF,
- хранения файлов в MinIO,
- авторизации и ролей через Keycloak.

## Состав сервисов
- `keycloak` (`8080`) - аутентификация/авторизация.
- `nsi` (`8001`) - справочники и правила.
- `conversion` (`8003`) - расчет конвертации по данным NSI.
- `documents` (`8002`) - накладные, расчет, генерация файлов.
- `documents_worker` - Celery worker для фоновых задач.
- `rabbitmq` (`5672`, `15672`) - брокер задач Celery.
- `minio` (`9000`, `9001`) - объектное хранилище файлов.

## Быстрый старт
1. Подготовить переменные:
   - `Copy-Item .env.example .env -Force`
2. Поднять backend-контур:
   - `docker compose up --build -d`
3. Поднять frontend:
   - `docker compose --profile ui up -d frontend`
4. Открыть:
   - UI: `http://localhost:5173`
   - Keycloak: `http://localhost:8080`

## Health-check
- NSI: `http://localhost:8001/healthz`
- Documents: `http://localhost:8002/healthz`
- Conversion: `http://localhost:8003/healthz`

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

## Admin reset (test mode)
- Realm role: `system.admin`
- Default admin user (realm import): `administrator` / `administrator`
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

Ветка `sb-security-fixes` создана как отдельный SB-контур: её задача — быть источником правды для hardened VPS-конфигурации, пока изменения не перенесены в канон. Актуальное live-состояние VPS должно совпадать именно с ней, а не с устаревшими ручными hotfix поверх `test`.

В рамках приведения проекта в соответствие с требованиями ИБ для VPS-профиля зафиксированы следующие требования:

1. **Изоляция сервисов:** Сервисы (RabbitMQ, MinIO, Keycloak) убраны с публичных интерфейсов и теперь слушают только `127.0.0.1`. Наружу смотрит только Nginx.
2. **Режим Keycloak:** Keycloak переведен из dev-режима в production (`start` вместо `start-dev`).
3. **Запуск без root:** Все основные приложения в контейнерах (nsi, documents, conversion, celery-воркеры) теперь запускаются от непривилегированного пользователя (UID 65532).
4. **Разделение сетей:** Контейнеры разнесены по изолированным сетям (`converter_frontend`, `converter_backend`, `converter_db`).
5. **Фиксация версий:** Использование `latest` тегов заменено на конкретные версии с привязкой к `sha256` хэшам образов.
6. **Отключение автодеплоя:** Автоматический деплой из GitHub на VPS отключен.
7. **Шифрование БД:** PostgreSQL TLS включён по умолчанию; Django использует `sslmode=verify-full`, Keycloak — `verify-server`.
8. **Безопасное хранение секретов:** Runtime env вынесен из checkout в `/etc/converter/.env` (права `0600`).
9. **RabbitMQ только по TLS:** plaintext AMQP `5672` отключён; используется только `5671` с peer verification и client certificates для `documents` / `documents_worker`.
10. **MinIO TLS без `cert_check=False`:** `documents` / `documents_worker` проверяют внутренний сертификат MinIO через локальную CA.

**Ожидает завершения:**
* **Настройка сетевого экрана (UFW):** Порты 443 и 22 пока открыты глобально. Мы ожидаем выделения IP-адреса терминального сервера и списка IP корпоративного контура от инфраструктурной команды. Как только данные будут получены, доступ будет строго ограничен этими адресами.
