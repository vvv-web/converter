# Аудит СБ — область ветки `sb-security-fixes`

Ветка **`sb-security-fixes`** в форке `vvv-web/converter` — **отдельный контур под требования Службы безопасности**. Ветка создана **специально для СБ**; описания «локальной разработки» и старый dev-compose **удалены** — единый hardened-манифест для VPS и проверок.

## Для проверяющего ИБ (с чего начать)

| № | Артефакт | Ссылка (ветка `sb-security-fixes`) |
|---|----------|-----------------------------------|
| 1 | **Прод-стек (единственный контракт VPS)** | [`docker-compose.vps.yml`](../docker-compose.vps.yml) |
| 2 | Чеклист статуса Converter | [`docs/security-sb-checklist.md`](security-sb-checklist.md) |
| 3 | MinIO, upload, `MINIO_ROOT_USER` | [`docs/security-sb-file-upload-and-minio.md`](security-sb-file-upload-and-minio.md) |
| 4 | Шаблон env (без секретов) | [`deploy/vps/.env.example`](../deploy/vps/.env.example) |
| 5 | Runbook VPS / approved deploy | [`deploy/vps/README.md`](../deploy/vps/README.md) |
| 6 | Автопроверка compose (как в CI) | [`.github/scripts/check_vps_compose_security.py`](../.github/scripts/check_vps_compose_security.py) |
| 7 | Проверка MinIO + отсутствие upload | [`scripts/security-verify-minio-and-upload-posture.sh`](../scripts/security-verify-minio-and-upload-posture.sh) |
| 8 | Соответствие резолюциям ИБ (Чумаков / Булатов) | [`docs/security-sb-requirements-mapping.md`](security-sb-requirements-mapping.md) |
| 9 | Канон формулировок R-* (все проекты) | https://github.com/vvv-web/security-board-requirements |

**Живой хост:** checkout `/opt/converter` на ветке `sb-security-fixes`, секреты только в **`/etc/converter/.env`** (chmod `600`, не в git).

## CI (не VPS)

GitHub Actions проверяет тот же `docker-compose.vps.yml` (через `include` в `docker-compose.yml`). **Аудит VPS и служебка ИБ** — только таблица выше; CI не является целевым контуром эксплуатации.

Скриншоты с **`${MINIO_ROOT_USER:-minio}`** — **устаревший** compose; в ветке: **`${MINIO_ROOT_USER:?set MINIO_ROOT_USER}`**.

## Вне области аудита VPS

| Путь | Почему не для служебки |
|------|-------------------------|
| `docs/RUNBOOK.md`, `docs/PROJECT_OVERVIEW_CANVAS.md` | Исторические обзоры; порты/схемы могут не совпадать с VPS |
| `frontend/README.md` | Сборка UI; периметр — Nginx + Keycloak на VPS |
| Профиль compose `ui` | Опционально для сборки; **не** публикуется в аудит периметра |

## Соответствие live VPS

- Источник правды для развёртывания на VPS — **эта ветка**, не `test` с ручными hotfix.
- После `git pull` на сервере: `docker compose --env-file /etc/converter/.env -f docker-compose.vps.yml config` и скрипты проверки из таблицы выше.

## После приёмки СБ

Перенос в канон (`test` / upstream) — отдельный merge/релиз; до переноса формулировки требований — в `security-board-requirements`, статус выполнения — в `docs/security-sb-checklist.md` этой ветки.
