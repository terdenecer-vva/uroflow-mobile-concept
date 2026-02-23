# Claims Governance v0.1 (MVP)

Дата: 2026-02-23
Назначение: контроль публичных и продуктовых утверждений (claims)

## 1) Цель

Исключить риск регуляторного дрейфа и несоответствия evidence-базе:
- все утверждения должны соответствовать intended use;
- любые новые claims проходят formal review;
- запрещённые формулировки блокируются до публикации.

## 2) Категории claims

`C1: Measurement claims` (разрешены при наличии evidence)
- Пример: "Приложение оценивает Qmax, Qavg, Vvoid по записи с iPhone".

`C2: Monitoring claims` (разрешены с оговорками)
- Пример: "Поддерживает динамическое наблюдение между визитами".

`C3: Diagnostic claims` (запрещены в MVP)
- Пример: "Диагностирует обструкцию/нейрогенный мочевой пузырь".

`C4: Therapeutic claims` (запрещены в MVP)
- Пример: "Рекомендует лечение/изменяет терапию".

## 3) Матрица разрешений по каналам

| Канал | C1 | C2 | C3 | C4 |
|---|---|---|---|---|
| In-app UI | allow | allow-with-disclaimer | block | block |
| PDF report | allow | allow-with-disclaimer | block | block |
| Website/marketing | allow-reviewed | allow-reviewed | block | block |
| Sales deck | allow-reviewed | allow-reviewed | block | block |
| Scientific poster | allow-with-methods | allow-with-methods | block-unless-approved-study | block |

## 4) Обязательные дисклеймеры MVP

- "Приложение не устанавливает диагноз и не назначает лечение".
- "Результат с низким quality-score требует повторного измерения".
- "Клинические решения принимаются медицинским специалистом".

## 5) Phrase library (разрешённые формулировки)

Разрешено:
- "оценка параметров урофлоуметрии"
- "мониторинг динамики"
- "инструмент поддержки наблюдения"

Запрещено:
- "ставит диагноз"
- "выявляет заболевание автоматически"
- "назначает/корректирует лечение"

## 6) Процесс утверждения новых claims

1. Инициатор создаёт Claim Change Request (CCR).
2. Указывает канал, аудиторию, текст claim, evidence-ссылки.
3. Review board: `RA/QA + Clinical + Product + Legal`.
4. Решение: approve / approve-with-changes / reject.
5. При approve обновляется claim registry и release notes.

SLA review: до 5 рабочих дней для стандартного CCR.

## 7) Claim Registry (минимальный формат)

| Поле | Описание |
|---|---|
| `claim_id` | Уникальный идентификатор |
| `category` | C1/C2/C3/C4 |
| `text` | Формулировка |
| `channels` | Где разрешено |
| `evidence_refs` | Ссылки на документы/отчёты |
| `owner` | Ответственный |
| `status` | active/deprecated/pending |
| `approved_at` | Дата утверждения |

## 8) Release gate для контента и UI

Перед каждым релизом:
- [ ] Сверка UI-текстов с Claim Registry
- [ ] Сверка маркетинговых материалов с approved claims
- [ ] Проверка наличия обязательных дисклеймеров
- [ ] Подпись RA/QA на claim-compliance checklist

## 9) Триггеры внепланового пересмотра

- изменение intended use;
- новая клиническая evidence-база;
- регуляторный фидбек/замечания;
- инцидент misleading claim.

## 10) Связанные документы

- `docs/intended-use-v1.md`
- `docs/regulatory-matrix-ru-cn-eu-us-v0.1.md`
- `docs/clinical-protocol-one-pager-v0.1.md`
