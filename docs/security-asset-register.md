# Реестр активов (шаблон под СБ)

Заполняется для служебки / аудита. **Секреты и пароли сюда не пишем** — только идентификаторы и роли.

| Актив | Назначение | FQDN / hostname | Публичный IP (если есть) | Среда | Владелец / контакт |
|-------|------------|-----------------|--------------------------|-------|-------------------|
| VPS Converter | Converter VPS runtime | `zvezda` / `converter.acom-offer-desk.ru` | `155.212.160.162` | prod | Acom / Converter ops |
| Keycloak | IdP внутри Converter runtime | `converter.acom-offer-desk.ru/auth` | `155.212.160.162` через host Nginx | prod | Acom / Converter ops |
| Converter backend services | NSI, Documents, Conversion APIs | `converter.acom-offer-desk.ru/{nsi,docs,conversion}` | `155.212.160.162` через host Nginx | prod | Acom / Converter ops |

**Проверка актуальности:** раз в релиз сверять DNS и `ss -tlnp` на хосте с таблицей (см. `docs/security-admin-access.md`).
