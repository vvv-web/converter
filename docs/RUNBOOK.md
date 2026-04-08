# RUNBOOK

## 0. Live-контур на VPS
- Публичный адрес: `https://converter.acom-offer-desk.ru`
- Актуальный источник кода для VPS: upstream `https://github.com/vldsmelov/converter.git`
- Актуальная ветка live-контура: `test`
- Автодеплой настроен на стороне VPS через `systemd`:
  - timer: `converter-autodeploy-test.timer`
  - service: `converter-autodeploy-test.service`
  - script: `/usr/local/bin/converter-autodeploy-test.sh`
- Если нужно именно VPS-операционное описание, см. `deploy/vps/RUNBOOK.md`

### Базовая проверка live-контура
- Health checks:
  - `curl -fsS https://converter.acom-offer-desk.ru/nsi/healthz`
  - `curl -fsS https://converter.acom-offer-desk.ru/docs/healthz`
  - `curl -fsS https://converter.acom-offer-desk.ru/conversion/healthz`
- Проверка автодеплоя:
  - `systemctl status converter-autodeploy-test.timer`
  - `journalctl -u converter-autodeploy-test.service -n 50 --no-pager`

## 1. Сервисы и порты
- `keycloak`: `8080`
- `nsi`: `8001`
- `documents`: `8002`
- `conversion`: `8003`
- `rabbitmq`: `5672`, `15672`
- `minio`: `9000`, `9001`

## 2. Основной поток данных
1. Пользователь логинится в Keycloak.
2. UI создает накладную в `documents`.
3. `documents` запускает задачу `calculate_invoice`.
4. Задача получает service-token (`documents-service`) и вызывает `conversion`.
5. `conversion` читает NSI и возвращает результат конвертации.
6. `documents` сохраняет `ConvertedLine`.
7. `documents` запускает генерацию XLSX/PDF и кладет файлы в MinIO.

## 3. Что важно по текущей версии
- NSI:
  - добавлены удаление для ЕИ, категорий, упаковок и правил;
  - добавлено редактирование упаковок;
  - в правилах добавлены вкладки по типам и редактирование каждого типа.
- Экспорт документов:
  - итоговые файлы имеют русские заголовки колонок;
  - выводится название товара (не только `item_id`);
  - PDF поддерживает кириллицу через `DejaVuSans`.

## 4. Проверка состояния
- Health:
  - `GET /healthz` на `nsi`, `documents`, `conversion`
- OpenAPI:
  - NSI: `/api/schema/`, `/api/docs/`
  - Documents: `/api/schema/`, `/api/docs/`
- Контейнеры:
  - `docker compose ps`
  - `docker compose logs --tail 200 documents documents_worker conversion nsi`

## 5. Полезные команды
- Полный старт:
  - `docker compose up -d --build`
- UI:
  - `docker compose --profile ui up -d frontend`
- Ручной сидинг:
  - `docker compose run --rm seed`
- Пересобрать только документы:
  - `docker compose up -d --build documents documents_worker`
- Остановить и очистить:
  - `docker compose down -v --remove-orphans`

## 6. Тесты и проверки
- Frontend build:
  - `docker run --rm -v ${PWD}:/repo -w /repo/frontend node:20-alpine sh -lc "npm ci && npm run build"`
- E2E:
  - `docker compose --profile tools run --rm e2e pytest -q tests/test_invoice_flow.py`
  - `docker compose --profile tools run --rm e2e pytest -q tests/test_end_to_end.py`
- Python smoke (`documents`):
  - `docker compose run --rm documents python -m py_compile apps/documents_core/rendering.py apps/documents_core/tasks.py`

## 7. Диагностика типовых проблем

### PDF ошибка по кириллице (Helvetica)
- Симптом: `Character "..." is outside the range ... helvetica`.
- Проверка: убедиться, что `documents` образ пересобран и перезапущен.
- Команда:
  - `docker compose up -d --build documents documents_worker`

### Файл с устаревшим форматом колонок
- Причина: файл был сгенерирован до обновления рендера.
- Действие: на карточке накладной повторно выполнить `Сгенерировать XLSX/PDF`.

### В колонке "Товар" снова виден `item_id`
- Проверить:
  - фронтенд отправляет `context.item_name`,
  - `documents` может сходить в NSI (`NSI_BASE_URL`, service-token).

## 8. Роли доступа
- NSI: `nsi.uom.*`, `nsi.item.*`, `nsi.package.*`, `nsi.rule.*`
- Conversion: `conversion.convert`, `conversion.ping`
- Documents: `documents.invoice.read|write|calculate|generate`

## 9. CI (кратко)
- `frontend-build`: `npm ci && npm run build`
- `python-smoke`: compile/check python
- `e2e-smoke`: поднимает compose-контур и гоняет e2e
