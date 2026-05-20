# Frontend (Vite + React + TypeScript)

> **Ветка `sb-security-fixes`:** UI для аудита периметра **не** является предметом служебки. На VPS пользователи заходят через **Nginx :443** + Keycloak. Сборка UI — опциональный профиль compose `ui` / `frontend` (loopback).

## Сборка (опционально, не VPS-аудит)

```bash
# из корня репозитория — тот же hardened-стек, что на VPS:
docker compose --env-file deploy/vps/.env.example -f docker-compose.vps.yml up -d --build \
  keycloak nsi documents
docker compose --env-file deploy/vps/.env.example -f docker-compose.vps.yml --profile ui up -d frontend
```

Порты по умолчанию в профиле — **loopback** (см. `docker-compose.vps.yml`). Не использовать как описание публичного периметра.

## Основные экраны

- Накладные: список, карточка, расчёт и генерация XLSX/PDF, скачивание.
- Создание накладной: конструктор строк, проверка правил конвертации.

Документация для ИБ: [`docs/SECURITY-SB-AUDIT-SCOPE.md`](../docs/SECURITY-SB-AUDIT-SCOPE.md).
