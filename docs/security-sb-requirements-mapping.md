# Соответствие резолюциям ИБ (ветка `sb-security-fixes`)

Ветка создана **специально под СБ**. Источник правды на VPS: **`docker-compose.vps.yml`** + **`/etc/converter/.env`**.

Канон формулировок R-*: [vvv-web/security-board-requirements](https://github.com/vvv-web/security-board-requirements).

---

## Резолюция М.С. Чумаков (технические замечания к compose)

| № | Требование ИБ | Статус в ветке | Где проверить |
|---|---------------|----------------|---------------|
| 1 | Сервисы не должны быть доступны с хоста без привязки к **127.0.0.1** (Redis, RabbitMQ, MinIO, Keycloak) | **Закрыто** | `docker-compose.vps.yml` — все `ports:` с `127.0.0.1:`; **Redis в стеке отсутствует** |
| 2 | Keycloak не в **dev-mode** | **Закрыто** | `command: start` (+ `--import-realm`), не `start-dev` |
| 3 | Redis без аутентификации | **N/A** | Redis не используется; брокер — RabbitMQ с `RABBITMQ_DEFAULT_USER` / `PASS` |
| 4 | MinIO не от **root** (Linux) | **Закрыто** | `user: "65532:65532"`; `MINIO_ROOT_USER` — имя S3-учётки |
| 5 | Межконтейнерный TCP без TLS | **Частично** | RabbitMQ **amqps:5671**, Postgres **SSL**, MinIO **HTTPS** внутри сети; HTTP между Django-сервисами — см. [security-sb-mtls-scope.md](security-sb-mtls-scope.md) |
| 6 | Одна сеть Docker | **Закрыто** | `converter_frontend`, `converter_backend`, `converter_db` (`internal: true` у db) |

Автопроверка compose: `.github/scripts/check_vps_compose_security.py`  
Ручная проверка MinIO/upload: `scripts/security-verify-minio-and-upload-posture.sh`

---

## Резолюция Д.А. Булатов (организация + контур)

| Требование | Статус | Комментарий |
|------------|--------|-------------|
| Снаружи только **443** (МЭ / firewall) | **ИБ / ЦОД** | Настраивается UFW/Nginx на хосте; в git — [security-sb-organizational-controls.md](security-sb-organizational-controls.md) |
| Запрет прямого доступа к портам кроме 443 | **Техника + ИБ** | Compose не публикует сервисы на `0.0.0.0`; финально — `ss -tlnp` + правила МЭ |
| Внешний доступ запрещён | **ИБ** | Политика периметра |
| Запрет `git pull` из ЦОД на сервер | **Процесс** | Выкат только **approved deploy** — [deploy/vps/README.md](../deploy/vps/README.md) |
| Админы только через терминальный сервер | **Процесс** | SSH-политика организации |
| **Keycloak + 2FA** | **Закрыто / эксплуатация** | Realm + `CONFIGURE_TOTP`; см. [infra/keycloak/README-SB.md](../infra/keycloak/README-SB.md), чеклист § Live verification |
| Ролевая модель, least privilege | **Закрыто / эксплуатация** | Realm roles в Keycloak; RBAC в API |
| Сканирование образов | **Процесс + скрипт** | `scripts/security-sbom-scan.sh`; регламент ИБ |
| Контейнеры **не от root** | **Закрыто** | Dockerfile `USER`; MinIO 65532; проверка `docker top` |
| **Шифрование БД** | **Закрыто** | PostgreSQL TLS — [security-db-encryption.md](security-db-encryption.md) |

---

## Что считается «вне ветки СБ»

Следующее **не входит** в область аудита этой ветки (может остаться в репозитории для CI, но не описывает VPS-контур):

- Исторические заметки с портами `5672` / `8080` на всех интерфейсах — см. только файлы из таблицы в [SECURITY-SB-AUDIT-SCOPE.md](SECURITY-SB-AUDIT-SCOPE.md).
- Профиль `ui` / `frontend` в compose — внутренняя сборка UI, **не** предмет служебки по периметру VPS.

---

## Live VPS

- Checkout: `/opt/converter`, ветка **`sb-security-fixes`**
- Env: **`/etc/converter/.env`** (не коммитить, не выводить в чат)
- Команда стека: `docker compose --env-file /etc/converter/.env -f docker-compose.vps.yml …`
