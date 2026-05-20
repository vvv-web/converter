# Загрузка файлов пользователем и MinIO — позиция для СБ (Converter)

**Назначение:** приложение к служебной записке ИБ. Фиксирует фактическое поведение системы по результатам разведки кода (ветка `sb-security-fixes`).

**Дата разведки:** 2026-05-19

---

## 1. Краткий вывод (для СЗ)

1. **Converter — калькулятор накладных**, а не файлообменник. Пользователь вводит **данные в форме** (JSON), а не загружает файлы с диска.
2. **Эндпоинта загрузки файлов нет** — ни в API (`documents`, `nsi`, `conversion`), ни во фронтенде (`<input type="file">` отсутствует).
3. **Пользователь не может записывать объекты в MinIO** — в MinIO попадают только **XLSX и PDF**, сгенерированные сервером после кнопки «Сгенерировать».
4. **MinIO на production не работает от root ОС** — в `docker-compose.vps.yml` задано `user: "65532:65532"`. Переменная **`MINIO_ROOT_USER`** — это **имя учётной записи S3-API** внутри MinIO, **не** UID 0 в Linux.
5. Сценарий «подсунуть вредоносный файл через веб» к **текущей** версии **не применим** (N/A). Отдельный антивирус при upload **не требуется**, пока нет приёма чужих файлов.
6. **MinIO можно исключить из контура** отдельным решением бизнеса, если откажутся от хранения/скачивания готовых Excel/PDF; **расчёт конвертации** от MinIO **не зависит**.

---

## 2. Поток данных (что реально происходит)

| Шаг | Действие | Формат | MinIO |
|-----|----------|--------|-------|
| 1 | Логин | Keycloak (OIDC) | — |
| 2 | Создать накладную | `POST /api/v1/invoices/` — JSON (`number`, `supplier`, `lines[]`) | — |
| 3 | Рассчитать | `POST …/calculate/` → Celery → `POST /api/v1/convert` (JSON) | — |
| 4 | Сгенерировать | `POST …/generate/` → Celery `generate_invoice_outputs` | **Запись** `.xlsx`, `.pdf` |
| 5 | Скачать | `GET …/files/{id}/download/` (JWT) | **Чтение** |

Источники в репозитории: `docs/RUNBOOK.md`, `docs/PROJECT_OVERVIEW_CANVAS.md`,  
`services/documents/apps/documents_core/views.py`, `tasks.py`,  
`frontend/src/pages/CreateInvoicePage.tsx`, `InvoiceDetailPage.tsx`.

---

## 3. Проверка: нет пользовательской загрузки

| Проверка | Результат |
|----------|-----------|
| `UploadFile`, `FileField`, `multipart` upload в Python-сервисах | **Не найдено** |
| `presigned_put`, `PUT` объекта от клиента | **Не найдено** |
| `<input type="file">`, `FormData` во фронтенде | **Не найдено** |
| Единственные `put_object` / `get_object` | `services/documents/apps/documents_core/tasks.py`, `views.py` (сервер) |

**API documents (полный список бизнес-маршрутов):**

- `GET/POST /api/v1/invoices/`, `GET/PATCH/DELETE …/invoices/{id}/`
- `POST …/invoices/{id}/calculate/`, `POST …/invoices/{id}/generate/`
- `GET …/invoices/{id}/files/{file_id}/download/` — только **выдача** сгенерированного файла
- `GET/POST/PATCH /api/v1/feedback/` — только текстовые поля
- `POST /api/v1/admin/reset-defaults/` — только `system.admin`

Сервисы **nsi** и **conversion** с MinIO **не связаны** (`docker-compose.vps.yml`: `depends_on` без minio у `conversion`, `nsi`).

---

## 4. MinIO: назначение и границы

| Вопрос | Ответ |
|--------|--------|
| Зачем MinIO? | Временное хранение **готовых** XLSX/PDF по накладной до скачивания |
| Кто пишет? | Только `documents_worker` (Celery), задача `generate_invoice_outputs` |
| Кто читает? | `documents` API (`download_file`) и опционально `presigned_url` (GET, ~15 мин) — в UI используется `download_url` с JWT |
| Публичный доступ к bucket? | **Нет** — MinIO на `127.0.0.1:29000`, TLS, внутренняя сеть Docker |
| Это «root» в Linux? | **Нет** на VPS — см. §5 |

Поле `presigned_url` в JSON API **не означает** загрузку: это **временная ссылка на скачивание** (аналог presigned GET в S3).

---

## 5. MinIO и «root» — разъяснение для СБ

### 5.1. Production (`docker-compose.vps.yml`)

```yaml
minio:
  user: "65532:65532"
```

Процесс `minio server` в контейнере работает от UID/GID **65532**, не от **0**.

### 5.2. Переменная `MINIO_ROOT_USER`

- Это **логин администратора API MinIO** (аналог access key), задаётся в env. Имя ключа **фиксировано MinIO** (vendor); переименовать переменную нельзя.
- **Не** означает запуск контейнера от суперпользователя Linux.
- В `docker-compose.vps.yml` **нет** fallback `:-minio` — только `${MINIO_ROOT_USER:?set MINIO_ROOT_USER}`.
- На VPS: свой логин (например `converter_storage`), **не** `minio` / `root`; пароль — `MINIO_ROOT_PASSWORD` (только в `/etc/converter/.env`, chmod 600, не в git).

### 5.3. Команды проверки на VPS (без секретов)

Выполнять на хосте с доступом к Docker (после `ssh` на сервер приложения):

```bash
cd /opt/converter
docker compose --env-file /etc/converter/.env -f docker-compose.vps.yml ps minio documents documents_worker

docker top converter-minio-1
docker top converter-documents-1

# Ожидаемо: USER 65532 (или числовой UID 65532) у minio и python, не root
```

Либо одним скриптом из репозитория:

```bash
./scripts/security-verify-minio-and-upload-posture.sh
```

### 5.4. Локально и CI (тот же `docker-compose.vps.yml`)

В ветке **`sb-security-fixes`** отдельного dev-compose нет: MinIO везде с **`user: 65532:65532`** и `${MINIO_ROOT_USER:?set …}`. Перед первым `up` — `./scripts/compose-preflight-tls.sh`.

---

## 6. Остаточные риски (не «загрузка файла»)

| Риск | Митигация / статус |
|------|---------------------|
| Инъекция через **текст** в полях накладной (формулы Excel) | Планируется уточнение санитизации при генерации XLSX |
| Нагрузка от злоупотребления «Рассчитать» / «Сгенерировать» | Keycloak + роли; rate limit — по политике ИБ |
| Компрометация учётной записи | 2FA Keycloak, least privilege |
| Появление **нового** upload в будущем | Отдельное согласование СБ (карантин, AV, лимиты) |

---

## 7. Опция: отказ от MinIO

Если бизнес подтвердит отказ от хранения готовых документов:

- **Удаляются:** сервис `minio`, volume `minio_data`, задачи записи в object storage, кнопки «Скачать» (или замена на генерацию «на лету» при скачивании).
- **Сохраняются:** Keycloak, NSI, conversion, documents (накладные, расчёт).

Это **отдельный релиз**, не блокер для заключения СБ по текущей версии.

---

## 8. Связанные документы

- `docs/security-sb-checklist.md` — трекер пунктов
- `docs/security-sb-delivery-pack.md` — пакет для ИБ
- [vvv-web/security-board-requirements](https://github.com/vvv-web/security-board-requirements) — R-F1, R-F2 (object storage)

---

*При изменении API (появление upload) этот документ подлежит пересмотру.*
