# Linear Import Seed v0.1

Дата: 2026-02-24

## Файлы

- `backlog-v0.1-linear-import.csv` — готовый CSV для импорта задач.
- `backlog-v0.1-linear-import.json` — тот же backlog в JSON-формате для API/скриптов.

## Формат CSV

CSV собран под поля, которые Linear описывает для импорта:
- `Title`
- `Description`
- `Priority`
- `Status`
- `Assignee`
- `Created`
- `Completed`
- `Labels`
- `Estimate`

Источник: [Linear Importer](https://linear.app/docs/import-issues)

## Как импортировать

1. В Linear открыть `Settings -> Administration -> Import/Export`.
2. Экспортировать пример CSV из Linear (чтобы сверить локальные названия статусов/полей).
3. При необходимости скорректировать `Status` и `Labels` под вашу workspace-конвенцию.
4. Импортировать `backlog-v0.1-linear-import.csv`.

## Примечания

- Поле `Assignee` оставлено пустым, чтобы распределить задачи после импорта.
- При отличающихся workflow-статусах замените `Backlog` на ваш начальный статус.
- В JSON можно добавить `team`/`project` перед программным созданием через API.
