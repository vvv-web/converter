# Политика портов (ветка `sb-security-fixes`)

Единственный контракт для VPS и аудита ИБ: **`docker-compose.vps.yml`**.

## Публикация на хосте

Все сервисы стека Converter слушают на хосте **только loopback**:

| Сервис | Привязка на хосте |
|--------|-------------------|
| Keycloak | `127.0.0.1:18080` |
| NSI | `127.0.0.1:18001` |
| Documents | `127.0.0.1:18002` |
| Conversion | `127.0.0.1:18003` |
| RabbitMQ TLS | `127.0.0.1:25671` |
| RabbitMQ management | `127.0.0.1:25673` |
| MinIO API / console | `127.0.0.1:29000` / `29001` |

PostgreSQL **не** публикуется на хост. Plaintext AMQP **5672** **отключён** (`listeners.tcp = none`).

Снаружи для пользователей — **только Nginx :443** (и при необходимости редирект :80 по политике ИБ).

## Проверка на VPS

```bash
ss -tlnp | grep -E '18080|18001|18002|25671|29000'
docker compose --env-file /etc/converter/.env -f docker-compose.vps.yml config | grep -A1 'ports:'
```

Не должно быть `0.0.0.0:<порт сервиса Converter>`. Публичный **:5432** на этом хосте относится к **`order_database`**, не к стеку Converter.
