# PrismaLite_API_Reference

Полная спецификация REST API PrismaLite. Формат ответов — JSON, аутентификация — JWT RS256 (`Authorization: Bearer <token>`). Версия API: `v1`.

## 1. Auth

### POST /auth/login
Request:
```json
{"login":"admin","password":"secret"}
```
Response:
```json
{"access_token":"<JWT>","refresh_token":"<RT>","expires_in":3600}
```

### POST /auth/refresh
Request:
```json
{"refresh_token":"<RT>"}
```
Response: новый access_token.

### GET /auth/public_key
Возвращает JWKS/pem:
```json
{"alg":"RS256","public_key":"-----BEGIN PUBLIC KEY-----..."}
```

## 2. System Health

- `GET /health/live` — жив ли сервис (без БД).
- `GET /health/ready` — готовность (БД, очередь, видео).
- `GET /metrics` — Prometheus.

## 3. Events API

### POST /api/v1/events/ingest
Headers: `Content-Type: application/json`, `X-Signature` (опционально).
Request:
```json
{
  "tenant_id": 1,
  "store_id": 10,
  "pos_id": "001-01",
  "cashier": "C105",
  "timestamp": "2025-01-19T12:11:44Z",
  "event_code": 20,
  "payload": {"sku":"4601234567890","qty":1,"price":249}
}
```
Response:
```json
{"status":"ok","event_id":553242}
```
Errors: `400 EVENT_CODE_INVALID`, `409 EVENT_DUPLICATE`, `429 RATE_LIMIT`.

### GET /api/v1/events/by_check/{check_id}
Response:
```json
[
  {"event_id":553242,"code":20,"timestamp":"2025-01-19T12:11:44Z","payload":{...}},
  ...
]
```

### GET /api/v1/events/latest?store_id=&limit=
Возвращает последние события.

## 4. Checks API

### GET /api/v1/checks/{check_id}
Response:
```json
{
  "check_id":553244,
  "check_number":"001-000123",
  "store_id":10,
  "pos_id":"001-01",
  "cashier":"C105",
  "start_ts":"2025-01-19T12:10:00Z",
  "end_ts":"2025-01-19T12:15:00Z",
  "total":249.00,
  "status":"closed",
  "events":[...]
}
```

### GET /api/v1/checks/search
Query params: `store_id`, `pos_id`, `cashier`, `from`, `to`, `sku`, `min_total`, `max_total`, `status`, `limit`, `offset`.

## 5. Incidents API

### GET /api/v1/incidents
Query: `store_id`, `pos_id`, `cashier`, `rule_code`, `severity`, `status`, `date_from`, `date_to`, `page`, `size`.
Response:
```json
{
  "items": [
    {"id":104522,"rule_code":"R020","status":"open","severity":3,"timestamp":"...","cashier":"C0021"}
  ],
  "total":120,
  "page":1,
  "size":20
}
```

### POST /api/v1/incidents/create
```json
{
  "rule_code":"MANUAL",
  "event_id":553242,
  "check_id":553244,
  "severity":2,
  "comment":"Manual incident"
}
```
Response: `{ "id": 200123 }`.

### PATCH /api/v1/incidents/{id}/status
```json
{"status":"closed","comment":"Confirmed"}
```

## 6. Rules API

- `GET /api/v1/rules` — список правил.
- `POST /api/v1/rules`
```json
{
  "code":"R999",
  "category":"custom",
  "description":"Custom rule",
  "severity":3,
  "params":{"threshold":2},
  "enabled":true
}
```
- `PATCH /api/v1/rules/{id}` — обновление (enabled, params, scope).

## 7. Video API

### GET /api/v1/video/live
Query: `camera_id`.
Response:
```json
{
  "camera_id":"cam01",
  "hls_url":"https://video.example.com/hls/live/cam01/index.m3u8?token=...",
  "expires_in":60
}
```

### GET /api/v1/video/replay
Query: `camera_id`, `from`, `to`.
Response: `{ "playlist":"https://.../hls/replay/cam01/....m3u8" }`

### GET /api/v1/video/snapshot
Query: `camera_id`, `timestamp`.
Response:
```json
{
  "image":"data:image/jpeg;base64,..."
}
```

Errors: `401 DVR_AUTH_FAILED`, `404 VIDEO_ARCHIVE_NOT_FOUND`, `503 DVR_OVERLOADED`.

## 8. Reports API

### POST /api/v1/reports/generate
```json
{
  "type":"incidents",
  "format":"pdf",
  "filters":{"store_id":10,"date_from":"2025-01-01","date_to":"2025-01-31"}
}
```
Response: `{ "report_id":"rep-123" }`

### GET /api/v1/reports/{report_id}
Возвращает статус/ссылку для скачивания.

## 9. Licensing API

- `GET /api/v1/license/status`
```json
{
  "valid": true,
  "expires": "2026-01-01",
  "cameras_allowed": 32,
  "cameras_used": 18,
  "registers_allowed": 64,
  "registers_used": 40
}
```
- `POST /api/v1/license/activate`
```json
{"key":"PL-XXXX-XXXX-XXXX"}
```

## 10. Admin API

- `POST /api/v1/admin/users`
```json
{"login":"analyst1","password":"Strong!Pass1","role":"ANALYST","stores":[1,2]}
```
- `PATCH /api/v1/admin/users/{id}` — смена роли, пароля, статуса.
- `GET /api/v1/admin/users`

- `POST /api/v1/admin/shops`
```json
{"tenant_id":1,"name":"Shop01","address":"..."}
```
- `POST /api/v1/admin/registers`
- `POST /api/v1/admin/cameras`

## 11. Error format

Все ошибки:
```json
{
  "error":"EVENT_CODE_INVALID",
  "message":"Неизвестный код события",
  "details":{"field":"event_code"}
}
```

Статусы:
- 400 — ValidationError.
- 401 — Auth required.
- 403 — Forbidden/ACL.
- 404 — Not found.
- 409 — Conflict (дубликат).
- 429 — Rate limit.
- 500 — Internal error (с `trace_id`).

## 12. WebSocket (план)

- `/ws/live` — уведомления об инцидентах, live события (подписка по магазинам).
- Сообщения:
```json
{"type":"incident","data":{"id":104522,"rule_code":"R020","status":"open"}}
```

## 13. Версионность и пагинация

- Версия API в URL (`/api/v1/...`).
- Пагинация: `page`, `size`, `total`, `items`.
- Rate limit заголовки: `X-RateLimit-Limit`, `X-RateLimit-Remaining`.

## 14. Swagger / OpenAPI

- Документация доступна на `/docs` (Swagger UI) и `/openapi.json`.
- Обновляется через CI при изменении API.

Документ дополняется по мере расширения API.

