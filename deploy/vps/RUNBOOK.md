# Converter на VPS (ветка `test`)

Публичный URL: `https://converter.acom-offer-desk.ru`

## Актуальный статус контура

- Канонический live-контур на VPS сейчас работает от **upstream-репозитория** `https://github.com/vldsmelov/converter.git`
- Рабочая ветка на сервере: `test`
- Текущий зафиксированный rollout при актуализации этого runbook: commit `3bbcdbc`
- Автодеплой сделан **на стороне VPS** через `systemd`, а не через GitHub Actions в репозитории руководителя

Причина такого решения простая: у рабочего аккаунта были права чтения на upstream-репозиторий, но не права записи, поэтому workflow в репозитории руководителя не настраивался. Обновление кода и деплой берёт на себя сам VPS.

## Git: откуда тянуть код на VPS

| Роль | Репозиторий | Примечание |
|------|-------------|------------|
| **Канон для live-деплоя на VPS** | `https://github.com/vldsmelov/converter.git` | upstream-репозиторий руководителя |
| **Локальный форк разработчика** | любой персональный fork | можно использовать для локальной разработки, но **не** как источник истины для VPS |

**Ветка для live-деплоя на VPS:** `test`

Первичное развёртывание с нуля на сервере:

```bash
git clone -b test https://github.com/vldsmelov/converter.git /opt/converter
cd /opt/converter
```

## Что где лежит

| Путь на сервере | Назначение |
|-----------------|------------|
| `/opt/converter` | репозиторий + `docker-compose.vps.yml` |
| `/opt/converter/deploy/vps/.env` | секреты и переменные (не в git) |
| `/var/www/converter` | статика Vite (собранный `frontend/dist`) |
| `/etc/nginx/sites-enabled/converter.acom-offer-desk.ru` | reverse proxy + TLS (certbot) |
| `/usr/local/bin/converter-autodeploy-test.sh` | VPS-side скрипт автодеплоя ветки `test` |
| `/etc/systemd/system/converter-autodeploy-test.service` | one-shot service для выката |
| `/etc/systemd/system/converter-autodeploy-test.timer` | таймер, который проверяет upstream и запускает service |

## Что было сделано при переводе на `test`

Перед переключением были сохранены контрольные точки:

- backup текущего каталога: `/opt/converter-backups/converter-20260408_105924`
- снапшот старого live-каталога до замены: `/opt/converter.pretest-20260408_105944`

После этого live-каталог `/opt/converter` был переведён на git-backed checkout ветки `test` из upstream-репозитория, а VPS-специфика возвращена поверх checkout:

- `docker-compose.vps.yml`
- `deploy/vps/.env`
- `deploy/vps/keycloak-import/realm-export.json`
- `deploy/vps/nginx-converter.acom-offer-desk.ru.conf`

## Порты на loopback (конфликт с `:8080` на хосте)

Сервисы слушают только `127.0.0.1`:

- Keycloak: `18080` → nginx `/auth/`
- NSI: `18001` → `/nsi/`
- Documents: `18002` → `/docs/`
- Conversion: `18003` → `/conversion/`
- MinIO API: `29000` → `/documents/` (bucket `documents`)
- MinIO console: `29001` (не проксируется наружу)
- RabbitMQ: `25672` / management `25673`

## Обновление кода с GitHub вручную

`origin` на VPS должен указывать на **`vldsmelov/converter`**, ветка — **`test`**.

```bash
cd /opt/converter
git remote -v   # проверка: origin → github.com/vldsmelov/converter.git
git fetch origin test
git checkout test
git reset --hard FETCH_HEAD
```

Пересборка и перезапуск бэкенда:

```bash
docker compose -f docker-compose.vps.yml --env-file deploy/vps/.env up -d --build
docker compose -f docker-compose.vps.yml --env-file deploy/vps/.env run --rm seed
```

## Автодеплой ветки `test`

На VPS настроен сценарий без GitHub Actions в upstream-репозитории:

1. `converter-autodeploy-test.timer` раз в минуту запускает `converter-autodeploy-test.service`
2. service вызывает `/usr/local/bin/converter-autodeploy-test.sh`
3. скрипт делает `git fetch origin test`
4. если commit не изменился, выката нет
5. если commit новый, скрипт:
   - обновляет checkout,
   - собирает frontend,
   - синхронизирует `/var/www/converter`,
   - выполняет `docker compose up -d --build`,
   - выполняет `seed`,
   - проверяет три публичных `healthz`

Проверка состояния автоматики:

```bash
systemctl status converter-autodeploy-test.timer
systemctl status converter-autodeploy-test.service
journalctl -u converter-autodeploy-test.service -n 50 --no-pager
```

## Обновление только фронтенда

На машине с Node/Docker (как в README репозитория):

```bash
docker run --rm -v "$PWD/frontend":/app -w /app node:20-alpine sh -lc \
  'npm ci && VITE_KEYCLOAK_URL=https://converter.acom-offer-desk.ru/auth \
   VITE_KEYCLOAK_REALM=uom VITE_KEYCLOAK_CLIENT_ID=frontend \
   VITE_NSI_BASE_URL=https://converter.acom-offer-desk.ru/nsi \
   VITE_DOCS_BASE_URL=https://converter.acom-offer-desk.ru/docs \
   npm run build'
```

Затем на VPS:

```bash
rsync -av --delete frontend/dist/ root@VPS:/var/www/converter/
# или scp/tar без rsync
chown -R www-data:www-data /var/www/converter
```

## Секреты и Keycloak

- `S2S_CLIENT_SECRET` в `.env` **должен совпадать** с `secret` клиента `documents-service` в `deploy/vps/keycloak-import/realm-export.json`.
- В git-репозитории `deploy/vps/keycloak-import/realm-export.json` хранится **шаблонный** вариант без живых секретов; рабочие значения для live-контура держим на VPS.
- После смены realm-файла при уже заполненной БД Keycloak может потребоваться сброс тома `converter_keycloak_db` (потеря данных IdP) или ручное обновление клиента в админке.

## Проверки

```bash
curl -fsS https://converter.acom-offer-desk.ru/nsi/healthz
curl -fsS https://converter.acom-offer-desk.ru/docs/healthz
curl -fsS https://converter.acom-offer-desk.ru/conversion/healthz
```

На момент последней актуализации этого файла все три endpoint возвращали `ok`.

## TLS

Сертификат: `certbot certificates | grep converter`. Автообновление — таймер certbot.

## Тестовые учётки (из realm import)

- Оператор: `operator` / `operator`
- Админ: `administrator` / `administrator`
- Keycloak master: см. `KEYCLOAK_ADMIN` / `KEYCLOAK_ADMIN_PASSWORD` в `.env` на сервере

Смените пароли для любого доступа вне песочницы.
