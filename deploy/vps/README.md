# VPS / СБ — артефакты в форке

**Форк:** `https://github.com/vvv-web/converter`

**SB-ветка:** `sb-security-fixes` — источник правды для hardening-контура VPS. Именно эта ветка должна совпадать с live-конфигурацией `converter` на хосте, пока замечания СБ не будут полностью перенесены в канон.

**Канон (upstream):** `https://github.com/vldsmelov/converter`, рабочая ветка выката обычно **`test`**.

## Актуальность форка относительно `test`

На машине разработчика:

```bash
git remote add fork https://github.com/vvv-web/converter.git   # один раз
git remote update
git rev-parse origin/test    # vldsmelov
git rev-parse fork/test      # vvv-web
```

Если SHA **совпадают** — ветка `test` форка выровнена с `test` канона. Для security-контура проверяйте отдельно `fork/sb-security-fixes`: именно она должна описывать текущий VPS hardening без drift-а.

Локальный клон может иметь `origin` на vldsmelov или на форк — ориентируйтесь на URL `git remote -v`.

## Файлы

| Файл | Назначение |
|------|------------|
| `../docker-compose.vps.yml` | Прод-стек: loopback-порты, пины версий образов, без dev bind-mount кода. |
| `.env.example` | Шаблон переменных; реальный env-файл живёт на сервере в `/etc/converter/.env` и **не коммитится**. |
| `nginx/converter-upstreams.conf.example` | Пример upstream на `127.0.0.1` для Nginx на хосте. |
| `keycloak-import/README.md` | Куда класть prod JSON realm без секретов. |
| `manual-approved-deploy.sh.example` | Ручной approved deploy: fetch, проверка commit, approval marker, backup, compose up. |
| `systemd/converter-autodeploy-test.sh.example` | Deprecated guard: старый unattended reset больше не используется. |
| `AUTODEPLOY-SB-NOTES.md` | Сопоставление autodeploy vs approved deploy для аудита СБ. |
| `SECRET-STORAGE-NOTES.md` | Кратко: права на `.env`, ротация, направление к Vault. |
| `../../scripts/security-sbom-scan.sh` | Локальный/CI запуск SBOM и vulnerability scan через Trivy или Syft+Grype. |

Дополнительно: `docs/security-*.md`, `infra/keycloak/README-SB.md`.

## Быстрый старт на сервере

```bash
sudo install -d -m 0750 -o root -g deploy /etc/converter
sudo cp deploy/vps/.env.example /etc/converter/.env
sudo chown root:deploy /etc/converter/.env
sudo chmod 0600 /etc/converter/.env
# отредактировать секреты, TLS paths и домены
./scripts/compose-preflight-tls.sh   # первый раз: postgres/rabbit/minio TLS
docker compose --env-file /etc/converter/.env -f docker-compose.vps.yml up -d --build
```

Однократный seed (профиль `bootstrap`): см. комментарии в `docker-compose.vps.yml`.

## SB baseline для security branch

- PostgreSQL TLS включён по умолчанию (`ssl=on`, Django через `sslmode=verify-full`, Keycloak через `verify-server`)
- RabbitMQ принимает только `amqp/ssl` на `5671`, plaintext `5672` отключён
- `documents` и `documents_worker` проверяют сертификат RabbitMQ и MinIO по локальной CA
- Все сервисы публикуют наружу только loopback-порты; внешний контур обслуживает host Nginx
- Секреты и runtime TLS-ключи не лежат в git

Перед первым SB deploy подготовьте runtime TLS-артефакты:

```bash
./deploy/vps/generate-postgres-tls.sh
./deploy/vps/generate-rabbitmq-mtls.sh
```

`generate-postgres-tls.sh` делает корневой каталог доступным на чтение для non-root приложений, а `generate-rabbitmq-mtls.sh` при запуске от root сразу выставляет корректных владельцев:
- `999:999` для server key/cert RabbitMQ
- `65532:65532` для client key/cert, которые читают `documents` и `documents_worker`

Сгенерированные ключи и сертификаты остаются только на сервере или в защищённом операторском контуре, не в git.

## Ручной approved deploy вместо unattended reset

СБ-режим для VPS: оператор явно выбирает commit, проверяет его и создаёт marker подтверждения. Скрипт делает только `git merge --ff-only`; `git reset --hard` в approved deploy не используется.

```bash
cd /opt/converter
git fetch origin test
git log --oneline --decorate -n 5 HEAD..FETCH_HEAD
APPROVED_COMMIT="$(git rev-parse FETCH_HEAD)"
touch "/opt/converter/.approved-deploy-${APPROVED_COMMIT}"
EXPECTED_COMMIT="${APPROVED_COMMIT}" /usr/local/bin/converter-manual-approved-deploy.sh
```

Рабочий скрипт на сервере берётся из `deploy/vps/manual-approved-deploy.sh.example` и устанавливается без суффикса `.example`, например в `/usr/local/bin/converter-manual-approved-deploy.sh` с правами `750`. Реальные секреты остаются только в `/etc/converter/.env` на VPS.

Перед выкатыванием СБ-изменений без секретов:

```bash
docker compose --env-file /etc/converter/.env -f docker-compose.vps.yml config --format json >/tmp/converter-vps-compose.json
python3 .github/scripts/check_vps_compose_security.py /tmp/converter-vps-compose.json deploy/vps/.env.example
./scripts/security-sbom-scan.sh
```
