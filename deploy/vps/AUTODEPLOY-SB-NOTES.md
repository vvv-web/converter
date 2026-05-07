# Autodeploy и СБ: заметки для аудита

## Контраст сценариев

| Аспект | Типичный `converter-autodeploy-test.sh` на VPS (исторический) | `manual-approved-deploy.sh.example` (рекомендуемый путь) |
|--------|----------------------------------------------------------------|----------------------------------------------------------|
| Выбор версии | Часто `git reset --hard` к `FETCH_HEAD` без явного human gate | Только `git merge --ff-only` к **заранее одобрённому** SHA |
| Подтверждение оператора | Нет или слабое | Обязательный **marker-файл** `.approved-deploy-<sha>` |
| Соответствие GitOps | Риск расхождения «что на диске» и «что в git» при сбое | Рабочее дерево проверяется на чистоту перед merge |
| Резервные копии | Зависит от реализации | Встроенные `pg_dump` и архив MinIO volume перед обновлением |

В репозитории пример **deprecated** autodeploy: `deploy/vps/systemd/converter-autodeploy-test.sh.example` (выходит с кодом 2 и текстом про переход на ручной approved deploy). **Рабочий скрипт на сервере** (`/usr/local/bin/converter-autodeploy-test.sh` и т.п.) мы **не удаляем** без явного решения оператора — только документируем риск.

## Рекомендация для ИБ / эксплуатации

1. Считать **небезопасным** любой unattended deploy с `reset --hard` к удалённой ветке без двухфакторного контроля (человек + фиксированный commit).
2. Перевести выкат на **`manual-approved-deploy.sh.example`**: установить как `/usr/local/bin/converter-manual-approved-deploy.sh`, выставить права `750`, вызывать только с `EXPECTED_COMMIT` и существующим marker.
3. Старый cron/systemd unit на autodeploy — **отключить** после пилотного прогона approved-скрипта.

## Шаги миграции (высокий уровень)

1. Сохранить копию текущего autodeploy-скрипта и unit/cron вне репозитория (бэкап).
2. Развернуть `manual-approved-deploy.sh.example` на сервер, проверить `shellcheck` / сухой прогон с неверным `EXPECTED_COMMIT` (должен отказать).
3. Один контролируемый выкат по инструкции из `deploy/vps/README.md` (fetch → log → marker → скрипт).
4. Отключить старый триггер autodeploy; задокументировать в журнале изменений ЦОД.

Подробные команды для оператора: `deploy/vps/README.md` (раздел про ручной approved deploy).
