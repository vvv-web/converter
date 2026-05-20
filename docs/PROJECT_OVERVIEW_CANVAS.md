# Converter — обзор-схема (вне аудита СБ)

> **Не использовать для служебки ИБ.** На ветке `sb-security-fixes` источник правды: [`docker-compose.vps.yml`](../docker-compose.vps.yml), [`README.md`](../README.md), [`security-sb-requirements-mapping.md`](security-sb-requirements-mapping.md).

Краткий «дашборд» по архитектуре (схема может содержать устаревшие порты **5672** / **8080**).

---

## 1. Карта сервисов (локальный compose)

```mermaid
flowchart LR
  subgraph clients
    UI[Frontend Vite\n:5173]
    KC_UI[Keycloak UI\n:8080]
  end

  subgraph auth
    KC[keycloak]
    KC_DB[(postgres keycloak)]
  end

  subgraph data
    NSI_DB[(postgres nsi)]
    DOC_DB[(postgres documents)]
    RMQ[rabbitmq\n5672 / UI 15672]
    S3[minio\n9000 API / 9001 console]
  end

  subgraph app
    NSI[nsi Django\n:8001]
    DOC[documents Django\n:8002]
    WRK[documents_worker\nCelery]
    CONV[conversion\n:8003]
  end

  UI --> KC
  UI --> NSI
  UI --> DOC
  KC --> KC_DB
  NSI --> NSI_DB
  NSI --> KC
  DOC --> DOC_DB
  DOC --> KC
  DOC --> RMQ
  DOC --> S3
  DOC --> CONV
  WRK --> RMQ
  WRK --> CONV
  WRK --> NSI
  WRK --> S3
  CONV --> NSI
```

---

## 2. Поток накладной (как в RUNBOOK)

```mermaid
sequenceDiagram
  participant U as Пользователь / UI
  participant K as Keycloak
  participant D as documents
  participant W as documents_worker
  participant C as conversion
  participant N as nsi
  participant M as MinIO

  U->>K: логин
  U->>D: создать накладную
  D->>W: задача calculate_invoice
  W->>C: конвертация (service token)
  C->>N: чтение НСИ / правил
  C-->>W: результат
  W->>D: сохранить ConvertedLine
  W->>M: XLSX/PDF в объектное хранилище
```

---

## 3. Таблица: сервис → порт → назначение

| Сервис | Порт (хост) | Назначение |
|--------|-------------|------------|
| keycloak | 8080 | SSO, realm `uom` |
| nsi | 8001 | НСИ, правила |
| documents | 8002 | Накладные, API файлов |
| conversion | 8003 | Расчёт конвертации |
| rabbitmq | 5672, 15672 | Celery |
| minio | 9000, 9001 | Файлы |
| frontend (profile `ui`) | 5173 | UI |

---

## 4. Health / быстрая проверка

| Проверка | URL / команда |
|----------|----------------|
| NSI | `GET http://localhost:8001/healthz` |
| Documents | `GET http://localhost:8002/healthz` |
| Conversion | `GET http://localhost:8003/healthz` |
| Контейнеры | `docker compose ps` |
| Логи | `docker compose logs --tail 200 documents documents_worker conversion nsi` |

---

## 5. Чеклист «всё живо»

- [ ] `docker compose ps` — все нужные сервисы `running` (и `documents_worker`).
- [ ] Три `/healthz` возвращают успех.
- [ ] Keycloak открывается, realm `uom` на месте (после импорта из `infra/keycloak`).
- [ ] При необходимости: `docker compose run --rm seed` — демо-данные.
- [ ] UI: `docker compose --profile ui up -d frontend` → `http://localhost:5173`.

---

## 6. CI (из README / RUNBOOK)

| Job | Суть |
|-----|------|
| frontend-build | `npm ci && npm run build` |
| python-smoke | проверки Python |
| e2e-smoke | compose + pytest e2e |

---

## 7. Продакшен (вне этого репо)

Код и compose — здесь; **URL, nginx, systemd, секреты на сервере** — по операционному runbook организации (ветка выката у мейнтейнера обычно `test`). В Git не кладут реальные `.env` и ключи.

---

*Файл для просмотра в IDE с превью Mermaid или экспорта в PNG через `mermaid-cli` при необходимости.*
