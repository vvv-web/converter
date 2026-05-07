# Пакет для передачи в СБ / ИБ (чеклист)

Используется при запросе «дистрибутивы, инструкции, отчёты». Состав может уточняться служебкой.

- [ ] Версии образов из `docker-compose.vps.yml` (теги + при необходимости `docker inspect` digest после `pull`).
- [ ] Вывод `docker save` или список образов + скрипт воспроизведения билда (без секретов).
- [ ] Результаты сканирования / SBOM — по регламенту ИБ (инструмент и версия указать в сопроводительном письме).
- [ ] Актуальный `docs/security-sb-checklist.md` с отмеченными пунктами.
- [ ] `docs/security-asset-register.md` (заполненный шаблон без секретов).
- [ ] Инструкция развёртывания: `deploy/vps/README.md` + `docs/RUNBOOK.md` §10.

## Команды для артефактов (выполнять из корня репозитория Converter)

**SBOM / скан уязвимостей** (нужен Docker; при офлайн-стенде — заранее подтянутые образы Trivy/Syft по регламенту):

```bash
./scripts/security-sbom-scan.sh
```

**Эффективный compose с разрешёнными digest образов** (нужен доступ к registry; на CI используется `docker compose … config` без `--resolve-image-digests` при недоступности):

```bash
docker compose --env-file deploy/vps/.env -f docker-compose.vps.yml config --resolve-image-digests > /tmp/converter-vps-compose-resolved.yml
```

Секреты из `deploy/vps/.env` в отчёт не копировать; для проверки инвариантов без секретов — как в CI: `docker compose -f docker-compose.vps.yml config --format json` с фиктивными переменными из `.github/workflows/ci.yml` и затем:

```bash
python3 .github/scripts/check_vps_compose_security.py /tmp/converter-vps-compose.json deploy/vps/.env.example
```

**Не включать:** `deploy/vps/.env`, ключи, пароли, приватные ключи TLS.
