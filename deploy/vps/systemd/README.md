# systemd: approved deploy без автосброса (СБ)

Файлы **не включают секреты**. Пути и пользователь `User=` задайте под свой хост.

## Deprecated: unattended timer

Старый hourly autodeploy больше не рекомендован: он мог подтянуть `test` и выполнить reset без ручного подтверждения. Файл `converter-autodeploy-test.sh.example` оставлен как deprecated guard и завершает работу с ошибкой.

## `/etc/systemd/system/converter-manual-approved-deploy.service`

```ini
[Unit]
Description=Converter approved deploy (branch test)
After=network-online.target docker.service

[Service]
Type=oneshot
User=root
WorkingDirectory=/opt/converter
Environment=REPO_DIR=/opt/converter
Environment=REMOTE=origin
Environment=BRANCH=test
EnvironmentFile=/etc/converter/approved-deploy.env
ExecStart=/usr/local/bin/converter-manual-approved-deploy.sh
```

Скрипт положить из репозитория: `deploy/vps/manual-approved-deploy.sh.example` → `/usr/local/bin/converter-manual-approved-deploy.sh`.

Файл `/etc/converter/approved-deploy.env` создаётся оператором перед запуском:

```bash
EXPECTED_COMMIT=<approved commit sha>
```

Approval marker должен существовать до запуска:

```bash
touch "/opt/converter/.approved-deploy-${EXPECTED_COMMIT}"
systemctl start converter-manual-approved-deploy.service
```

Таймер намеренно не приводится: deploy запускается только после явного approval.
