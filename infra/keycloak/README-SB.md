# Keycloak и СБ (форк / подготовка к прод)

## Что даёт `realm-export.json`

В репозитории — **частичный** экспорт realm `uom` для `--import-realm` при первом старте. Поля `otpPolicy*` задают параметры TOTP (6 цифр, 30 с) — это **не** включает обязательный 2FA для всех пользователей автоматически.

## Обязательный 2FA (требование СБ)

После поднятия Keycloak в прод-режиме (`start`, не `start-dev`):

1. В Admin Console: **Authentication → Flows → Browser** — добавить шаг OTP (или Conditional OTP) согласно [Server Administration Guide](https://www.keycloak.org/docs/latest/server_admin/).
2. Либо назначить пользователям **Required user action** `Configure OTP` (или политику realm для новых пользователей).

Параметры TOTP по умолчанию в **dev-импорте** realm (только справка, не замена шага 1–2): `infra/keycloak/realm-export.json` — поля `otpPolicyType`, `otpPolicyDigits`, `otpPolicyPeriod` и др.; они **не включают** обязательный 2FA для всех пользователей сами по себе.

Импорт JSON **пропускает** уже существующий realm при рестарте — изменения политик безопаснее вносить через Admin API/Console или отдельный controlled import.

VPS-safe шаблон без секретов: `deploy/vps/keycloak-import/realm-prod-template.json.example`. Он не содержит пользователей/паролей и сужает browser-client под prod origin.

## RBAC (роли и разграничение)

Проверка для аудита (выполнять в Admin Console после стабилизации realm):

1. **Realm roles / Client roles:** убедиться, что критичные операции (админка, массовые действия) привязаны к ролям, а не к «всем залогиненным».
2. **Service accounts:** клиенты `confidential` с service account — перечислить; минимизировать scope ролей по принципу least privilege.
3. **Пользователи vs сервисные УЗ:** операторские учётки в отдельной группе; S2S-клиенты не используют человеческие пароли из seed.
4. **Аудит:** включить/проверить событие логина и админских действий согласно политике ИБ (хранение и экспорт логов — на стороне хоста/ELK).

Детали клиентов и redirect: см. разделы ниже в этом файле.

Admin API runbook (выполнять на сервере, значения env не выводить):

```bash
docker compose -f docker-compose.vps.yml exec keycloak /opt/keycloak/bin/kcadm.sh config credentials \
  --server http://127.0.0.1:8080/auth \
  --realm "$KEYCLOAK_ADMIN_AUTH_REALM" \
  --user "$KEYCLOAK_ADMIN" \
  --password "$KEYCLOAK_ADMIN_PASSWORD"

docker compose -f docker-compose.vps.yml exec keycloak /opt/keycloak/bin/kcadm.sh update clients/<frontend-client-uuid> \
  -r uom \
  -s 'redirectUris=["https://converter.acom-offer-desk.ru/*"]' \
  -s 'webOrigins=["https://converter.acom-offer-desk.ru"]'
```

## Клиенты `redirectUris` / `webOrigins`

В dev-экспорте могут быть широкие шаблоны. Для прода сузить под реальный HTTPS-ориджин фронта (см. служебку СБ). Правки — в отдельной ветке форка и ревью перед merge в `test`.

## `KEYCLOAK_JWT_AUDIENCE`

Не включать вслепую: разные Keycloak-клиенты могут выдавать `aud` как `account`, client id frontend или список аудиторий. Без безопасной проверки фактического токена нельзя зафиксировать значение в Git.

Проверка без вывода токена:

```bash
TOKEN_JSON="$(curl -fsS -X POST "$CONVERTER_KEYCLOAK_ISSUER_PUBLIC/protocol/openid-connect/token" \
  -H 'Content-Type: application/x-www-form-urlencoded' \
  --data-urlencode 'grant_type=password' \
  --data-urlencode 'client_id=uom-cli' \
  --data-urlencode "username=$CHECK_USERNAME" \
  --data-urlencode "password=$CHECK_PASSWORD")"
TOKEN_JSON="$TOKEN_JSON" python3 - <<'PY'
import base64, json, os
token = json.loads(os.environ["TOKEN_JSON"])["access_token"]
payload = token.split(".")[1] + "=="
print(json.loads(base64.urlsafe_b64decode(payload))["aud"])
PY
```

После подтверждения значения задать `KEYCLOAK_JWT_AUDIENCE` только в server-side `deploy/vps/.env`.
