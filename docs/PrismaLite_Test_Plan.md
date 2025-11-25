# PrismaLite_Test_Plan

## 1. Цель

Определить стратегию тестирования PrismaLite: POS ingest, видео, backend, UI, интеграции, безопасность, нагрузка и регресс. План используется QA, DevOps и разработкой перед релизами.

## 2. Среды

| Среда | Назначение | Особенности |
|-------|------------|-------------|
| DEV | разработка, unit/integration | Shared DB, тестовые сообщения |
| STAGE | предпрод | Реплика PROD, копия конфигов |
| PERF | нагрузочное | Отдельные ресурсы, синтетика |
| PROD | продуктив | Только мониторинг/смоки |

Данные: синтетические + анонимизированные боевые логи.

## 3. POS Ingest Tests

### 3.1 Цели
- Проверить корректность приёма/нормализации событий (Set Retail, Frontol).
- Валидация бизнес-ограничений (чековые пары, dedup).
- Обработка ошибок и DLQ.

### 3.2 Тест-кейсы
1. **SET Retail XML** — полный чек (DOC_BEGIN→EVENTS→DOC_END), проверка записи в БД.
2. **SET Retail JSON** — новая схема.
3. **Frontol Log** — AddItem/Void/Payment.
4. **Invalid format** — повреждённый XML → ошибка, запись в DLQ.
5. **Duplicates** — повторные события → hash dedup.
6. **Latency** — задержанные события (±5 мин) → корректная привязка.

## 4. Video Module Tests

### 4.1 Live
- RTSP тестовый поток → HLS, проверка задержки, стабильности.
- Несколько одновременных потоков.

### 4.2 Archive
- Запрос `/video/replay` с периодом, проверка сегментов.
- Ошибка `VIDEO_ARCHIVE_NOT_FOUND`.

### 4.3 Errors
- Неверные креды (DVR_AUTH_FAILED).
- DVR offline (NetworkError).
- Overload (лимит сессий) → 503.

## 5. Backend Unit Tests

- Покрытие ≥ 60% core модулей.
- Тесты для: Rules Engine, Normalizer, Validator, ACL, Licensing, API handlers.
- Использовать pytest + factories/fixtures.

## 6. Integration Tests

- Backend ↔ PostgreSQL (миграции, CRUD).
- Backend ↔ Video (mock driver).
- Backend ↔ POS Agent (HTTP ingest).
- Backend ↔ License server.
- Проверка инцидента: событие → правила → запись в `incidents`.

## 7. End-to-End (E2E)

### 7.1 Базовый сценарий
```
POS Agent → Events → Backend → Rules Engine → Incident → UI отображает чек+видео → оператор закрывает инцидент
```

Шаги:
1. Симулировать чек (двойное сканирование).
2. Проверить запись в events/checks.
3. Проверить создание инцидента.
4. Открыть UI (Analytics), убеждаемся, что видео синхронизировано.
5. Изменить статус инцидента.

### 7.2 Вариации
- Возврат без оригинала.
- Маркировка (R010/R011).
- Live инцидент → оператор подтверждает/отклоняет.

## 8. Regression Tests

- Запускаются перед каждым релизом.
- Набор:
  - Авторизация.
  - Поиск чеков, фильтры.
  - Live мониторинг.
  - Создание/редактирование правил.
  - Инциденты (создание/изменение/экспорт).
  - Отчёты (генерация/скачивание).
- Автоматизация: Cypress/Playwright + API тесты.

## 9. Нагрузочные тесты

### 9.1 Event Storm
- Генерация 300–500 событий/сек (скрипт `scripts/stress_test_events.py`).
- Цель: проверить ingest latency, CPU, DB.

### 9.2 Video Storm
- 20 операторов × 4 камеры, суммарно 80 live потоков.
- Мониторинг `active_rtsp_sessions`, задержка сегментов.

### 9.3 Combined
- Одновременный Event + Video Storm.

### 9.4 Long-run
- 24–72 часа непрерывной работы.

## 10. Security Tests

- JWT: подпись, срок жизни, refresh reuse.
- ACL: доступ только в рамках tenant/store.
- Rate limiting + brute force.
- Validation против SQL/XSS/CSRF.
- Проверка HTTPS/TLS конфигураций.
- Pen-test (по запросу).

## 11. Smoke Tests (post-deploy)

1. `/health/ready` → 200.
2. POS agent `--simulate` → событие в UI.
3. Видео live + архив.
4. Инцидент создаётся и закрывается.
5. Отчёт «Incidents» генерируется.

## 12. Bug Tracking / Reporting

- Система: Jira/YouTrack.
- Severity: Blocker/Critical/Major/Minor.
- Отчёты: ежедневные/еженедельные QA summary.

## 13. Выходные критерии

- Все block/critical дефекты закрыты.
- Regression suite зелёный.
- Нагрузочные тесты удовлетворяют SLA.
- Security тесты без блокеров.
- Документация обновлена.

Документ актуализируется при изменении архитектуры, тестовых инструментов или требований.

