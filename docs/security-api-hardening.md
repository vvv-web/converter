# Ужесточение API в проде (СБ)

Следующие места в коде **намеренно мягкие для dev**; перед внешним контуром пройти ревью с ИБ:

| Область | Файлы / что сделать |
|---------|---------------------|
| OpenAPI / Swagger | `OPENAPI_PUBLIC_ENABLED` fail-closed: default `0` в Django settings; `/api/schema/`, `/api/docs/` включаются только при явном `OPENAPI_PUBLIC_ENABLED=1`. Если СБ разрешит публикацию, включать только за Nginx allowlist / Basic auth. |
| Анонимные read | `allow_anonymous_read` в NSI/Documents views — убедиться, что для прода не раскрывают лишние данные. |
| Conversion optional auth | Эндпоинты с `optional_bearer` — проверить, что без токена не отдаётся бизнес-логика. |

JWT: проверка `aud` включается переменной **`KEYCLOAK_JWT_AUDIENCE`** (см. `services/*/authn/authentication.py`, `services/conversion/app/main.py`). Без проверки фактического токена Keycloak значение не фиксировать: runbook безопасной проверки — `infra/keycloak/README-SB.md`.

Host header: в `docker-compose.vps.yml` `ALLOWED_HOSTS` задаётся через **`CONVERTER_ALLOWED_HOSTS`** (без `*` в прод/SB-профиле).
