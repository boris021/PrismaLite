# PrismaLite_Database_Design

Документ описывает модель данных PrismaLite, включая сущности, связи, правила целостности и рекомендации по развитию схемы. Он служит источником правды для backend, аналитики и DevOps.

## 1. Архитектурные принципы

- **Мульти-tenant**: каждый запрос привязан к `tenant_id`, который присутствует во всех пользовательских таблицах.
- **Событийная модель**: события кассовых систем являются центральным источником данных, вокруг которого строятся чеки, инциденты и видео.
- **Иммутабельность критичных журналов**: таблицы `events`, `audit_log` и `video_segments` не допускают обновлений за исключением сервисных полей.
- **Партиционирование по времени**: крупные таблицы делятся по месяцам/неделям для управления производительностью.

## 2. ER-диаграмма (ASCII)

```
 TENANT ──< SHOP ──< REGISTER ──< EVENTS ──< INCIDENTS
      \                             \               > CHECKS
       \                             > VIDEO_LINKS

 RULES ──< INCIDENTS
 USERS ──< AUDIT_LOG
 CAMERAS ──< VIDEO_SEGMENTS
```

## 3. Таблицы и поля

### 3.1 Tenants / Shops / Registers

| Таблица  | Поля                                                                 | Особенности                                           |
|----------|----------------------------------------------------------------------|-------------------------------------------------------|
| tenants  | `id SERIAL PK`, `name TEXT`, `status TEXT`, `created_at TIMESTAMPTZ` | `status`: active/suspended                            |
| shops    | `id SERIAL PK`, `tenant_id INT FK`, `name TEXT`, `address TEXT`      | Уникальный индекс `(tenant_id, name)`                 |
| registers| `id SERIAL PK`, `shop_id INT FK`, `tenant_id INT`, `pos_code TEXT`, `integration_type TEXT`, `status TEXT` | Уникальный индекс `(tenant_id, pos_code)`             |

### 3.2 Reference сущности

| Таблица | Поля | Примечания |
|---------|------|------------|
| users   | `id SERIAL PK`, `tenant_id INT`, `login TEXT UNIQUE`, `role TEXT`, `permissions JSONB`, `store_scope INT[]`, `created_at TIMESTAMPTZ` | Используется ACL |
| cameras | `id SERIAL PK`, `shop_id INT`, `register_id INT NULL`, `name TEXT`, `vendor TEXT`, `channel TEXT`, `rtsp_url TEXT`, `tenant_id INT`, `created_at TIMESTAMPTZ` | Привязка к кассе опциональна |

### 3.3 Events / Checks

| Таблица | Поля | Индексы / примечания |
|---------|------|----------------------|
| events  | `id BIGSERIAL PK`, `tenant_id INT`, `shop_id INT`, `register_id INT`, `check_id BIGINT NULL`, `event_code INT`, `timestamp TIMESTAMPTZ`, `cashier TEXT`, `payload JSONB`, `source TEXT`, `hash TEXT UNIQUE`, `video_ts TIMESTAMPTZ` | Индексы: `timestamp`, `event_code`, `tenant_id` |
| checks  | `id BIGSERIAL PK`, `tenant_id INT`, `shop_id INT`, `register_id INT`, `check_number TEXT`, `cashier TEXT`, `start_ts TIMESTAMPTZ`, `end_ts TIMESTAMPTZ`, `total NUMERIC(12,2)`, `status TEXT`, `currency TEXT`, `metadata JSONB` | Индекс `check_number`, `tenant_id` |

### 3.4 Rules / Incidents

| Таблица | Поля | Примечания |
|---------|------|------------|
| rules   | `id SERIAL PK`, `tenant_id INT NULL`, `code TEXT UNIQUE`, `category TEXT`, `description TEXT`, `severity INT`, `params JSONB`, `enabled BOOL`, `scope JSONB`, `created_at TIMESTAMPTZ` | `tenant_id NULL` — глобальные правила |
| incidents | `id BIGSERIAL PK`, `tenant_id INT`, `rule_code TEXT FK`, `event_id BIGINT FK`, `check_id BIGINT`, `shop_id INT`, `register_id INT`, `timestamp TIMESTAMPTZ`, `severity INT`, `status TEXT`, `payload JSONB`, `assignee INT NULL`, `video_link_id BIGINT NULL` | Индексы: `rule_code`, `status`, `timestamp` |

### 3.5 Video подсистема

| Таблица | Поля | Примечания |
|---------|------|------------|
| video_links | `id BIGSERIAL PK`, `event_id BIGINT FK`, `camera_id INT`, `start_ts TIMESTAMPTZ`, `end_ts TIMESTAMPTZ`, `confidence NUMERIC(5,2)` | Связка события и отрезка архива |
| video_segments | `id BIGSERIAL PK`, `camera_id INT FK`, `tenant_id INT`, `start_ts TIMESTAMPTZ`, `end_ts TIMESTAMPTZ`, `path TEXT`, `checksum TEXT`, `size_bytes BIGINT`, `retention_until TIMESTAMPTZ` | Партиционирование по дате |

### 3.6 Audit / Licensing

| Таблица | Поля | Примечания |
|---------|------|------------|
| audit_log | `id BIGSERIAL PK`, `tenant_id INT`, `user_id INT`, `action TEXT`, `ts TIMESTAMPTZ`, `ip INET`, `details JSONB` | Append-only, партиционирование по неделям |
| licenses | `id SERIAL PK`, `tenant_id INT`, `type TEXT`, `limit INT`, `used INT`, `expires_at TIMESTAMPTZ`, `last_check TIMESTAMPTZ` | Типы: `cash_registers`, `cameras`, `analysts` |

## 4. Связи

- `tenants 1:N shops`, `shops 1:N registers`, `registers 1:N events`.
- `checks 1:N events` через `check_id`.
- `rules 1:N incidents`, `events 1:N incidents`.
- `cameras 1:N video_segments`, `video_links` связывает `events` и `cameras`.
- `users 1:N audit_log`.

## 5. Партиционирование и индексы

| Таблица   | Партиционирование       | Индексы                                          |
|-----------|-------------------------|--------------------------------------------------|
| events    | RANGE по `timestamp` (месяц) | `idx_events_ts`, `idx_events_code`, `idx_events_tenant` |
| checks    | RANGE по `start_ts` (месяц)  | `idx_checks_number`, `idx_checks_tenant_ts`      |
| incidents | RANGE по `timestamp` (месяц) | `idx_incid_rule`, `idx_incid_status`, `idx_incid_tenant_ts` |
| audit_log | RANGE по неделям          | `idx_audit_user`, `idx_audit_action`             |
| video_segments | RANGE по `start_ts` (неделя) | `idx_video_cam_ts`                         |

## 6. Ограничения целостности

- Все ключевые таблицы содержат `tenant_id` и `FOREIGN KEY` на родительские сущности.
- События валидируются по `hash` для исключения дублей: `hash = sha256(tenant_id, register_id, timestamp, event_code, payload)`.
- `checks.total` проверяется триггером `CHECK` на неотрицательность.
- `incidents.severity` ограничен `CHECK (severity BETWEEN 1 AND 5)`.
- `rules.params` валидируются на уровне приложения (JSON Schema).

## 7. Потоки данных

1. **INGEST**: POS → `events` → обновление `checks`.
2. **Rules Engine**: события и чеки → `incidents`.
3. **Video**: DVR сегменты → `video_segments` → `video_links`.
4. **Audit**: действия пользователей → `audit_log`.

## 8. Рост и хранение

- `events`: ~1 млн/сутки ⇒ 30 млн/месяц ⇒ 15–20 ГБ/месяц (включая JSONB).
- `video_segments`: зависит от качества; рекомендуется отдельный диск/облако.
- Ротация: `events` хранить 12 месяцев, `video_segments` 7–30 дней (по политике).

## 9. Миграции и версии схемы

- Инструмент миграций: Alembic/Flyway (решается в backend).
- Версионирование: semver (`2025.01.0`), обязательные миграции сопровождаются release notes.
- Все ddl-изменения проходят через staging окружение с нагрузочным реплеем.

## 10. Нерешённые вопросы

| Тема | Вопрос | Ответственный |
|------|--------|---------------|
| Partition sizing | Подбор размера партиций для `events` при >5 млн/сутки | DBA |
| Video store | Использование S3 vs локального хранилища | DevOps + Video team |
| Rules customization | Персонификация правил per-tenant | Product + Backend |

Документ должен обновляться при любом изменении логической схемы или требований хранения данных.

