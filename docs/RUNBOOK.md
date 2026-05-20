# RUNBOOK (не для аудита СБ)

Ветка **`sb-security-fixes`** не использует этот файл.

**Проверяющему ИБ:** [`SECURITY-SB-AUDIT-SCOPE.md`](SECURITY-SB-AUDIT-SCOPE.md), [`security-sb-checklist.md`](security-sb-checklist.md), [`security-sb-requirements-mapping.md`](security-sb-requirements-mapping.md), [`docker-compose.vps.yml`](../docker-compose.vps.yml), [`deploy/vps/README.md`](../deploy/vps/README.md).

**Операции на VPS:** `docker compose --env-file /etc/converter/.env -f docker-compose.vps.yml …`, секреты только в `/etc/converter/.env`.
