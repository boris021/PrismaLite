# PrismaLite_Operations

## 1. Назначение

Руководство описывает эксплуатацию PrismaLite: мониторинг, резервное копирование, обновления, диагностику, логирование и тестирование работоспособности. Целевая аудитория — администраторы, DevOps, служба поддержки.

## 2. Мониторинг

### 2.1 Обязательные метрики

| Компонент | Метрики |
|-----------|---------|
| Backend | HTTP latency (avg/p95), `events_ingested_total`, `rules_latency_ms`, `db_pool_usage` |
| POS Agent | `events_buffered`, `events_sent`, `agent_offline_seconds` |
| Video Proxy | `active_rtsp_sessions`, `hls_sessions_total`, `dvr_errors_total`, `segment_latency_seconds` |
| PostgreSQL | `connections`, `replication_lag`, `table_size`, `dead_tuples` |
| License server | `license_checks_total`, `quota_usage` |

Экспортеры: Prometheus Node Exporter, PostgreSQL Exporter, custom endpoints `/metrics`.

### 2.2 Алерты

- Backend response time > 500 мс в течение 5 минут.
- Очередь POS агента > 500 событий.
- Нет событий от магазина > 10 минут.
- Video Proxy: >80% лимита RTSP сессий или рост `DVR_OVERLOADED`.
- PostgreSQL: свободное место < 15%, рост `dead_tuples`.
- License: истекает < 14 дней.

## 3. Резервное копирование

### 3.1 PostgreSQL
- Ежедневный full backup (`pg_dump` или `pg_basebackup`).
```
pg_dump -U prismlite -F c prismlite > D:\backups\prismlite_$(date).dump
```
- WAL-архивирование для point-in-time recovery.
- Хранение backup ≥ 30 дней, шифрование (gpg/AES).

### 3.2 HLS/Видео
- Ежедневная ротация/копирование сегментов (robocopy/rsync).
- Если используется S3 → lifecycle policies.
- Обязательно проверять свободное место и retention (7–30 дней).

### 3.3 Конфигурации и ключи
- Каталоги: `C:\PrismaLite\backend`, `video`, `agent`, `license`, `.env`, `keys`.
- Использовать защищённое хранилище (Vault, DPAPI).

## 4. Обновления (backend/video/agent/license)

1. Сообщить пользователям о maintenance окне.
2. Остановить сервис (`nssm stop` или `systemctl stop`).
3. `git pull`, `pip install -r requirements.txt`.
4. Выполнить миграции (`alembic upgrade head`).
5. Запустить сервис, проверить `/health/ready`.
6. Пройти smoke-тесты (п.7).

Видео и POS агент обновляются аналогично; если есть автообновление, проверить журналы.

## 5. Диагностика и troubleshooting

### 5.1 POS Agent
- Лог: `C:\PrismaLite\agent\logs\agent.log`.
- Команды:
```
python agent.py --status
python agent.py --simulate additem
```
- Частые проблемы: нет связи (firewall), неверный backend URL, заполненный offline buffer.

### 5.2 Backend
- Лог: `C:\PrismaLite\logs\backend\*.log`.
- Health-check: `curl http://localhost:8080/health/ready`.
- Проверка базы: `psql -c "SELECT count(*) FROM events WHERE timestamp > now() - interval '1 hour';"`.

### 5.3 Video Proxy
- Лог: `C:\PrismaLite\logs\video\video.log`.
- Health: `curl http://localhost:9000/health`.
- Проверить доступ к DVR: `ffmpeg -i rtsp://user:pass@dvr/... -t 5 -f null -`.

### 5.4 License Server
- `curl http://localhost:9001/status`.
- Лог: `logs/license/*.log`.

### 5.5 Общие шаги
1. Проверить логи.
2. Проверить сеть (ping, tracert).
3. Проверить свободное место (`Get-PSDrive`/`df -h`).
4. Проверить время (NTP).

## 6. Логирование

- Формат JSON:
```json
{"ts":"...","level":"INFO","service":"api","msg":"event_ingested","context":{"event_id":123}}
```
- Хранение: локальный диск + централизованный сбор (Loki/ELK).
- Ротация: 30–90 дней, audit — до 180 дней (регуляторика).
- Каталоги:
  - Backend: `logs/backend/`.
  - Video: `logs/video/`.
  - Agent: `agent/logs/`.
  - License: `logs/license/`.
- Audit log в БД (`audit_log`), доступ только у security/ops.

## 7. Тестирование работоспособности

### 7.1 POS ingest
```
python agent.py --simulate additem
curl http://backend/api/v1/events/latest
```

### 7.2 Видео
- Live: открыть UI → выбрать камеру.
- Архив: `curl "http://backend/api/v1/video/replay?camera_id=cam01&from=...&to=..."`.

### 7.3 Инциденты
- Отправить тестовый сценарий (двойное сканирование) → проверить `/incidents`.

### 7.4 Health + лицензии
- `curl http://backend/health/ready`
- `curl http://license/status`

### 7.5 Автоматические тесты
- `pytest` на backend (по графику, минимум 1 раз в неделю на prod-like).
- Smoke E2E (agent → backend → video → UI).

## 8. Регресс и контрольные списки

- При каждом релизе: чеклисты UI (логин, аналитика, live, инциденты).
- Проверить отчёты (`/reports/generate`).
- Проверить интеграции (Set Retail/Frontol) на тестовых логах.

## 9. Инциденты эксплуатации

### 9.1 Процесс
1. Классифицировать (P1 критический, P2 высокий, P3 средний).
2. Назначить ответственных (Ops, Backend, Video).
3. Собрать данные: логи, метрики, audit.
4. Принять меры (рестарт, переключение на резерв, hotfix).
5. Постмортем, обновление документации.

### 9.2 Типовые кейсы
- **Нет событий**: проверить POS Agent, сеть, license (квоты).
- **Нет видео**: DVR недоступен, истекли креды, проблемы с HLS.
- **БД перегружена**: вакуум, увеличение ресурсов, архивация старых партиций.
- **Лицензия**: превышены квоты, истёк срок — обратиться к лиценз-серверу.

## 10. Оптимизация и housekeeping

- Вакуум и анализ партиций `events` (еженедельно/ежедневно при больших объёмах).
- Архивирование старых логов и HLS сегментов.
- Контроль использования лицензий, отключение неиспользуемых касс/камер.
- Проверка партиций (`events`, `incidents`) — создание новых заранее.

## 11. Документы и ссылки

- `PrismaLite_Installation.md` — шаги установки.
- `PrismaLite_DevOps.md` — Docker/K8s/CI/CD, мониторинг.
- `PrismaLite_Test_Plan.md` — полный набор тестов.
- `PrismaLite_Security.md` — политики безопасности.

Документ актуализируется при изменении процессов эксплуатации и инструментов мониторинга.

