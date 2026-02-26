# Regulatory Matrix v0.1: РФ / Китай / ЕС / США

Дата: 2026-02-23
Версия: Draft v0.1
Назначение: рабочая матрица для планирования регистрации и клинического маршрута.

Важно: документ для планирования R&D и подготовки стратегии.
Финальные регуляторные решения принимаются с локальными RA/юристами.

## 1) Intended Use рамка для снижения рисков класса

Рекомендуемая стартовая формулировка claims:
- измеряет параметры урофлоуметрии (`Qmax`, `Qavg`, `Vvoid`, времена, форма кривой)
- поддерживает мониторинг и документирование динамики
- не ставит диагноз и не даёт терапевтических назначений

## 2) Матрица по регионам

## Россия (РФ)

Рабочая гипотеза:
- медицинское ПО с измерительной функцией;
- регистрационный маршрут по действующим правилам Росздравнадзора.

Ключевые требования к старту:
- пакет техдокументации и валидации;
- клинические данные сопоставимости с эталоном;
- управление рисками и quality management процесс.

Данные и приватность:
- учитывать требования локализации ПД граждан РФ;
- предпочтительно on-device default и/или инфраструктура БД в РФ.

Immediate actions:
- подтвердить класс риска и код номенклатуры с локальным RA;
- зафиксировать архитектуру данных для РФ-контура.

## Китай (NMPA)

Рабочая гипотеза:
- standalone medical software;
- измерительная функция требует сильной доказательной базы точности.

Ключевые требования к старту:
- четкий intended use без избыточных AI-claims;
- локальная стратегия валидации и досье по алгоритму.

Данные и приватность:
- учитывать режим sensitive PI и separate consent;
- заранее спроектировать локальный data governance контур.

Immediate actions:
- pre-gap assessment под NMPA software expectations;
- стратегия локализации клинических/технических evidence.

## ЕС (MDR)

Рабочая гипотеза:
- standalone software под Rule 11 (часто не ниже IIa при диагностической инфо).

Ключевые требования к старту:
- клиническая оценка и PMCF стратегия;
- техническая документация MDR (включая software lifecycle, risk, usability);
- QMS под ISO 13485.

Данные и приватность:
- health data как special category;
- explicit consent/правовая основа, minimization, privacy-by-default.

Immediate actions:
- утвердить границы claims, чтобы не поднять класс без необходимости;
- подготовить структуру technical documentation Annex II/III.

## США (FDA)

Рабочая гипотеза:
- software-driven urine flow/volume measuring function;
- класс и premarket-траектория зависят от конкретного intended use и характеристик.

Ключевые требования к старту:
- quality system соответствие (QMSR контур);
- software verification/validation пакет;
- cybersecurity документация для connected-варианта.

Данные и приватность:
- HIPAA применимость зависит от B2B-модели и роли (covered entity/BA).

Immediate actions:
- classification/regulatory strategy memo (включая exempt/non-exempt анализ);
- зафиксировать cybersecurity SBOM/patch/vuln disclosure процесс.

## 3) Cross-region document backbone (единый пакет)

Базовые артефакты, которые готовим один раз и адаптируем:
- Intended Use + Claims matrix
- Software Requirements Specification (SRS)
- Architecture & Data Flow docs
- Risk Management File (ISO 14971)
- Software V&V plan + reports
- Clinical Evaluation / Clinical Performance plan
- Usability Engineering File
- Cybersecurity file
- Post-market surveillance plan

## 4) Регуляторные стоп-факторы (что может остановить проект)

- claims выходят в автоматическую диагностику без достаточного evidence;
- нет трассируемости версии модели к клиническим данным;
- нет убедимой стратегии качества данных и артефактов;
- нет регионально корректной data governance модели.

## 5) 90-дневный регуляторный план

Недели 1-4:
- финализировать intended use и claims policy;
- провести региональный gap-analysis по документам.

Недели 5-8:
- подготовить v0.1 DHF skeleton;
- запустить risk management и cybersecurity workstream.

Недели 9-12:
- собрать pre-submission пакет (внутренний) для РФ first-pilot;
- подготовить адаптацию пакета для ЕС/США/Китая.
