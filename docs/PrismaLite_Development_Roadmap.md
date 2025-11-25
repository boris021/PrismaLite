# PrismaLite_Development_Roadmap

## 1. Подход

- Методология: Agile/Kanban, релизы каждые 2–4 недели.
- Основные ветки: `develop`, `release/*`, `main`.
- Критерии готовности этапа: выполнены задачи, покрыты тестами, обновлена документация.

## 2. Этапы

| # | Этап | Срок | Ключевые задачи | Зависимости | Критические точки |
|---|------|------|-----------------|-------------|-------------------|
| 1 | Архитектура | 2–3 недели | Архитектура backend/frontend/video, ER, API каркас | Vision, Security draft | Выбор технологий, протокол видео |
| 2 | БД | 2 недели | Создание таблиц, partitioning, индексы, миграции | Stage 1 | Производительность вставки 1M+/сутки |
| 3 | Backend Core | 4–6 недель | Auth, ACL, events ingest, normalizer, rules engine, audit, API | Stage 1–2, Security, Rules | Скорость обработки событий, связь с видео |
| 4 | POS Agent | 3–4 недели | Set Retail XML/JSON, Frontol logs/API, offline buffer, сервис | Stage 3, Integrations | Надёжность на 30+ магазинах |
| 5 | Video Module | 4–6 недель | DVR drivers, RTSP→HLS, архив, live UI API | Stage 3, Video Spec | RTSP стабильность, нагрузка |
| 6 | Frontend | 6–10 недель | Live мониторинг, аналитика (чек+видео), инциденты, настройки, auth | Stage 3/5, UI Guide | UX аналитики, синхронность видео |
| 7 | Licensing | 2 недели | Модель лицензий, ключи, backend integration | Stage 3 | Безопасность ключей |
| 8 | Reporting | 3–5 недель | Отчёты по кассирам/инцидентам, экспорт | Stage 3/6 | Большие выборки |
| 9 | Testing | 2–4 недели | Автотесты backend/video/agent, E2E, нагрузка | All previous | Нагрузочные сценарии |
|10 | Production Infra | 2–3 недели | Docker/K8s, CI/CD, мониторинг, бэкапы | Stage 3–7 | SLA, HA, ресурсы |
|11 | Pilot | 2 недели | Развёртывание на 1–2 магазина, сбор фидбека | Stage 9/10 | Стабильность, поддержка |
|12 | Release v1.0 | 1 неделя | Финальная сборка, документация, релиз-ноты | Stage 11 | ГОТО; freeze |

## 3. Диаграмма зависимостей (ASCII)

```
ARCH → DB → BACKEND → POS AGENT → VIDEO → FRONTEND → LICENSE → REPORTS → TESTS → PROD INFRA → PILOT → RELEASE
```

## 4. Риски и меры

| Риск | Описание | Митигация |
|------|----------|-----------|
| RTSP нестабилен | DVR не выдерживает нагрузку | Резервный поток, substream, балансировка |
| POS data quality | Логи повреждены/нет времени | Сильный нормализатор, DLQ, мониторинг |
| Rules latency | Обработка >300 мс | Оптимизация правил, кэш, масштабирование |
| БД рост | 1M+ событий/сутки | Partitioning, индексы, архив, масштабирование |
| Лицензии | Кража ключей | RS256, secure storage, аудиты |

## 5. Milestones и релизы

- **M1 (Month 1)**: Архитектура + БД.
- **M2 (Month 2)**: Backend Core + POS Agent MVP.
- **M3 (Month 3)**: Video + Frontend Alpha.
- **M4 (Month 4)**: Licensing + Reports + QA Alpha.
- **M5 (Month 5)**: Production infra + Pilot.
- **M6 (Month 6)**: Release v1.0.

## 6. Чеклисты готовности

- Этап 3 (Backend): API задокументированы, 60% тестов, ingestion stable.
- Этап 5 (Video): Live + Archive, DVR drivers покрыты, алерты.
- Этап 6 (Frontend): основные экраны готовы, UX review.
- Этап 9 (Testing): Regression green, нагрузочные тесты выполнены.
- Этап 12 (Release): все документы обновлены, training completed.

## 7. Post-release

- Наблюдение 2 недели (hypercare).
- План Minor релизов (v1.1, v1.2) — backlog features (ML, WebRTC).
- Retrospective и обновление roadmap.

Документ актуализируется ежеквартально Product Manager'ом и Solution Architect'ом.

