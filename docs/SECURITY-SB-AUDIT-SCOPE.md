# Аудит СБ — область ветки `sb-security-fixes`

Ветка **`sb-security-fixes`** в форке `vvv-web/converter` — **отдельный контур под требования Службы безопасности**, не замена ветки `test` / `main` для ежедневной разработки.

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
| 8 | Канон формулировок R-* (все проекты) | https://github.com/vvv-web/security-board-requirements |

**Живой хост:** checkout `/opt/converter` на ветке `sb-security-fixes`, секреты только в **`/etc/converter/.env`** (chmod `600`, не в git).

## Локально и CI (тот же hardened-стек)

| Файл | Роль |
|------|------|
| [`docker-compose.yml`](../docker-compose.yml) | Тонкий `include` → [`docker-compose.vps.yml`](../docker-compose.vps.yml) (без отдельного dev-стека). |
| [`.env.example`](../.env.example) | Шаблон для localhost (loopback-порты `180xx`, TLS как на VPS). |
| [`scripts/compose-preflight-tls.sh`](../scripts/compose-preflight-tls.sh) | Генерация TLS перед первым `docker compose up`. |
| Профиль `ui` / `frontend` | Vite на `127.0.0.1:15173`, бэкенд — loopback `18001`/`18002`/`18080`. |
| Профиль `tools` / `e2e` | CI: `docker compose -f docker-compose.vps.yml --profile tools run --rm e2e`. |

Скриншоты с **`${MINIO_ROOT_USER:-minio}`** относятся к **старой** версии compose; в актуальной ветке для MinIO: **`${MINIO_ROOT_USER:?set MINIO_ROOT_USER}`** (коммит `7d68832` и новее).

## Соответствие live VPS

- Источник правды для развёртывания на VPS — **эта ветка**, не `test` с ручными hotfix.
- После `git pull` на сервере: `docker compose --env-file /etc/converter/.env -f docker-compose.vps.yml config` и скрипты проверки из таблицы выше.

## После приёмки СБ

Перенос в канон (`test` / upstream) — отдельный merge/релиз; до переноса формулировки требований — в `security-board-requirements`, статус выполнения — в `docs/security-sb-checklist.md` этой ветки.
