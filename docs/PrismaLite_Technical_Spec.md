# PrismaLite_Technical_Spec

## 1. Архитектурный обзор

PrismaLite построена по модульной архитектуре с разделением на слои:

- **Frontend**: SPA (React/Vue) + WebSockets/WebRTC для live.
- **Backend**: Python FastAPI (рекомендовано) или Node.js/NestJS в микросервисном подходе.
- **Event Ingest Layer**: сервисы приёма событий (Set Retail, Frontol).
- **Rules Engine**: потоковая обработка событий, генерация инцидентов.
- **Video Layer**: DVR драйверы + RTSP→HLS proxy.
- **Database Layer**: PostgreSQL 14+, партиционированные таблицы.
- **Monitoring/Logging**: Prometheus + Grafana, Loki/ELK.

## 2. API (Backend)

### 2.1 Auth
- `POST /auth/login` — логин, возвращает JWT (RS256) + refresh.
- `POST /auth/refresh` — обновление токена.
- `GET /auth/public_key` — JWKS/публичный ключ.

### 2.2 Events API
- `POST /api/v1/events/ingest`
```json
{
  "pos_id": "001-01",
  "cashier": "C001",
  "timestamp": "2025-01-19T12:00:00Z",
  "event_code": 20,
  "payload": {"sku":"4601234567890","qty":1,"price":249}
}
```
- `GET /api/v1/events/by_check/{check_id}`
- `GET /api/v1/events/latest?store_id=&limit=`

### 2.3 Checks API
- `GET /api/v1/checks/{check_id}`
- `GET /api/v1/checks/search?store=&pos=&cashier=&from=&to=&sku=`

### 2.4 Incidents API
- `GET /api/v1/incidents?store=&rule_code=&status=&from=&to=`
- `POST /api/v1/incidents/create`
- `PATCH /api/v1/incidents/{id}/status`

### 2.5 Rules API
- `GET /api/v1/rules`
- `POST /api/v1/rules`
- `PATCH /api/v1/rules/{id}`

### 2.6 Video API
- `GET /api/v1/video/live?camera_id=` → `{ "hls_url": "...", "token": "..." }`
- `GET /api/v1/video/replay?camera_id=&from=&to=`
- `GET /api/v1/video/snapshot?camera_id=&ts=`

### 2.7 Licensing/API и System health
- `GET /api/v1/license/status`
- `POST /api/v1/license/activate`
- `GET /health/live`, `GET /health/ready`

Полная спецификация будет в `PrismaLite_API_Reference.md`.

## 3. Структуры данных (PostgreSQL)

Подробное описание таблиц — `PrismaLite_Database_Design.md`, SQL — `PrismaLite_DB_Schema.sql`. Кратко:

- `tenants`, `shops`, `registers` — иерархия клиентов.
- `events` — партиционированная таблица событий, JSONB payload.
- `checks` — документы продаж.
- `rules`, `incidents` — правила и зафиксированные нарушения.
- `cameras`, `video_segments`, `video_links` — видеомодуль.
- `users`, `audit_log`, `licenses`.

Индексы и партиционирование настроены по `timestamp`.

## 4. Архитектурные слои (подробно)

| Слой | Ответственность | Технологии |
|------|----------------|------------|
| Transport Layer | REST/WebSocket API, экспонирование сервисов | FastAPI/NestJS, ASGI |
| Application Layer | Бизнес-логика, правила, отчёты | Python сервисы, Celery |
| Domain Layer | Сущности Event, Check, Incident, Rule | Pydantic models / DTO |
| Infrastructure Layer | PostgreSQL, DVR драйверы, очереди | SQLAlchemy, Redis/Kafka |
| Integration Layer | POS агент, лицензирование, мониторинг | gRPC/REST, Prometheus |

## 5. Кодстайл и инструменты

- Python: PEP8, `black`, `ruff`, `mypy`.
- Node.js (при использовании): ESLint + Prettier.
- Tests: `pytest` / `vitest`, покрытие ≥ 60%.
- Коммит-месседжи: Conventional Commits.

## 6. Логирование и наблюдаемость

- Формат: JSON (`ts`, `level`, `service`, `msg`, `context`).
- Транспорт: stdout → Loki/ELK, часть логов в файл (`/logs/<service>/`).
- Трейсинг: OpenTelemetry (опционально).
- Метрики:
  - `events_ingested_total`, `incidents_created_total`.
  - HTTP latency p95/p99.
  - Video proxy: `active_rtsp_sessions`, `dvr_errors_total`.

## 7. Правила обработки и алгоритмы

### 7.1 Дедупликация событий
```
hash = sha256(tenant_id, register_id, timestamp, event_code, payload)
if exists(hash): discard
```

### 7.2 Правило R001 «Двойное сканирование»
1. Получить последнюю позицию чека.
2. Если `sku` совпадает и `Δt < 3s` → incident.

### 7.3 Сопоставление видео
```
video_ts = event.timestamp - offset_pre (5 сек)
segment = find_segment(camera_id, video_ts)
```

### 7.4 Retry/Backoff
- HTTP/RTSP запросы — retry 3 раза с exponential backoff (500ms, 1s, 2s).
- Circuit breaker для DVR по количеству ошибок.

## 8. Event Ingest Pipeline

1. **Gateway**: принимает XML/JSON/LOG, валидирует подписи, ставит в очередь (Kafka/RabbitMQ/Redis Streams).
2. **Normalizer**: приводит к единому JSON, маппит коды событий.
3. **Enricher**: добавляет `tenant_id`, `shop_id`, `register_id`, справочники.
4. **Validator**: проверка структуры, пар связок DOC_BEGIN/DOC_END, бизнес-ограничений.
5. **DB Writer**: пишет в `events`, обновляет `checks`, публикует в Rules Engine.

## 9. Video Layer

- Driver Interface:
```python
class DvrDriver:
    def connect(...)
    def get_live_rtsp(channel_id) -> str
    def get_replay_rtsp(channel_id, from_ts, to_ts) -> str
    def list_channels() -> list
    def get_recording_ranges(channel_id, day) -> list
```
- Реализации: `HikvisionDriver`, `DahuaDriver`, `CsiDriver`.
- Proxy-сервис использует ffmpeg/gstreamer для RTSP→HLS, хранит сегменты на локальном диске/S3.
- Tokens: `/video/live` выдаёт HLS URL с краткоживущим токеном.

## 10. DevOps требования

- Docker/Compose — минимальная среда.
- Kubernetes — deployments + services + ingress; HPA для backend и video.
- Secrets: JWT ключи, DVR креды, строки БД в K8s Secret или Vault.
- CI/CD: GitHub Actions/GitLab CI (lint → test → build → push → deploy).
- Бэкапы: pg_dump или basebackup + WAL archiving; видео — ротация 7–30 дней.
- Мониторинг: Prometheus, Grafana, Loki; алерты по таймингам, очередям ingest, нагрузке DVR.

## 11. Error Handling

- Единый формат ошибок:
```json
{ "error": "EVENT_CODE_INVALID", "message": "...", "details": {} }
```
- Категории:
  - ValidationError — HTTP 400.
  - AuthError — HTTP 401/403.
  - NotFound — HTTP 404.
  - Conflict/Duplicate — HTTP 409.
  - RateLimit — HTTP 429.
  - InternalError — HTTP 500 (с UUID инцидента).
- Видео-ошибки: `DVR_AUTH_FAILED`, `VIDEO_STREAM_ERROR`, `DVR_OVERLOADED`.

## 12. Security

- JWT RS256, приватный ключ хранится только на auth-сервисе.
- Tenant isolation на уровне БД (`tenant_id` во всех таблицах, Row-Level Filters).
- ACL проверяется на backend (`acl.check(user.role, permission)`).
- TLS для всех внешних соединений, DVR доступ только через backend-прокси.
- Audit log для действий пользователей и доступа к видео.
- Rate limiting и защита от replay (nonce, timestamp).

Подробности — в `PrismaLite_Security.md`.

## 13. Нагрузка и масштабирование

- Цели: ≥1 млн событий/сутки, ≥20 live потоков одновременно.
- Вертикальная масштабируемость DB (SSD, 32+ GB RAM), горизонтальная — реплики.
- Backend scale-out через Kubernetes (autoscaling по CPU/RPS).
- Video proxy масштабируется по числу камер (шардинг по магазинам).
- POS agents масштабируются по магазинам, каждый агент обслуживает несколько касс.

## 14. Release flow

1. Feature branch → Pull Request (CI: lint + tests).
2. Merge в `develop` → автодеплой на STAGE.
3. Нагрузочные/интеграционные тесты.
4. Tag `vX.Y.Z`, merge в `main`.
5. CI/CD: build images, миграции, деплой на PROD.

## 15. Открытые вопросы

| Тема | Вопрос | Ответственный |
|------|--------|---------------|
| Stream storage | S3 vs локальные диски для HLS сегментов | DevOps + Video |
| Rules customization | Tenant-специфические параметры правил | Product/Backend |
| License offline | Формат офлайн-активации | Product + Security |

Документ поддерживается архитектором системы и обновляется при изменении архитектуры или API.

