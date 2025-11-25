# PrismaLite_Installation

## 1. Общая информация

Руководство описывает установку PrismaLite на Windows Server 2019/2022 и включает развёртывание PostgreSQL, backend, POS агента, видеомодуля и лицензионного сервера. Используется для пилотов и продуктивных установок.

## 2. Инфраструктурные требования

| Компонент | Минимум | Рекомендовано |
|-----------|---------|---------------|
| Windows Server | 2019 Standard, 8 GB RAM, 4 CPU, SSD 100 GB | 2022, 16 GB RAM, 8 CPU, SSD 200 GB |
| PostgreSQL | v14+, 100 GB SSD | v14+, 500 GB SSD + реплика |
| Backend сервер | Python 3.11, 4 CPU, 8 GB RAM | 8 CPU, 16 GB RAM |
| Video Proxy | FFmpeg, 8 CPU, 16 GB RAM, диск 1 TB | 16 CPU, 32 GB RAM, отдельный массив |
| POS Agent | Windows/Linux кассовый сервер | --- |

Открытые порты: 80/443 (UI/API), 5432 (PostgreSQL), 8080 (backend), 9000 (HLS), 8554 (RTSP), 9001 (license), 9100+ (Prometheus exporters).

## 3. Предварительная подготовка

1. Установить обновления Windows, включить .NET Framework 4.8.
2. Установить PowerShell 7, Git, Python 3.11, Visual C++ Redistributable.
3. Настроить брандмауэр (разрешить необходимые порты).
4. Синхронизировать время через NTP.
5. Создать каталоги:
```
C:\PrismaLite\
  backend\
  video\
  agent\
  license\
  hls\
  logs\
```

## 4. Установка PostgreSQL

### 4.1 Установка
1. Скачать дистрибутив PostgreSQL 14+.
2. Во время установки выбрать компоненты: Server, Command Line Tools (pg_dump).
3. Указать порт 5432, пользователя `postgres`, задать пароль.

### 4.2 Настройка БД
```
psql -U postgres
> CREATE DATABASE prismlite;
> CREATE USER prismlite WITH PASSWORD 'StrongPass!';
> GRANT ALL PRIVILEGES ON DATABASE prismlite TO prismlite;
```

### 4.3 Создание схемы
```
psql -U prismlite -d prismlite -f docs/PrismaLite_DB_Schema.sql
```

## 5. Установка backend

### 5.1 Клонирование
```
cd C:\PrismaLite\backend
git clone https://repo/prismalite/backend.git .
```

### 5.2 Настройка окружения
Создать `.env`:
```
DB_HOST=localhost
DB_PORT=5432
DB_NAME=prismlite
DB_USER=prismlite
DB_PASS=StrongPass!
JWT_PRIVATE_KEY=C:\PrismaLite\keys\jwt_private.pem
VIDEO_PROXY_URL=http://localhost:9000
LICENSE_URL=http://localhost:9001
```

### 5.3 Установка зависимостей
```
py -3.11 -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

### 5.4 Миграции и запуск
```
alembic upgrade head
uvicorn app.main:app --host 0.0.0.0 --port 8080
```

### 5.5 Установка как Windows Service (NSSM)
```
nssm install PrismaLiteBackend "C:\PrismaLite\backend\.venv\Scripts\python.exe" "C:\PrismaLite\backend\run.py"
nssm set PrismaLiteBackend AppDirectory C:\PrismaLite\backend
nssm start PrismaLiteBackend
```

## 6. Установка Video Proxy

### 6.1 Клонирование и зависимости
```
cd C:\PrismaLite\video
git clone https://repo/prismalite/video-proxy.git .
pip install -r requirements.txt
```

### 6.2 Конфигурация `video.yaml`
```yaml
hls_output: C:/PrismaLite/hls/
log_path: C:/PrismaLite/logs/video.log
dvr:
  vendor: hikvision
  host: 192.168.1.10
  port: 554
  login: admin
  password: secret
```

### 6.3 Запуск
```
python proxy.py
```
Рекомендуется настроить как Windows Service (аналогично backend).

## 7. Установка POS Agent

### 7.1 Клонирование
```
cd C:\PrismaLite\agent
git clone https://repo/prismalite/pos-agent.git .
pip install -r requirements.txt
```

### 7.2 Конфигурация `config.yaml`
```yaml
backend_url: https://backend.example.com/api/v1/events/ingest
tenant_id: 1
store_id: 10
pos_type: setretail
log_path: C:/PrismaLite/agent/logs/
retry:
  attempts: 5
  backoff_ms: 500
```

### 7.3 Тест и запуск
```
python agent.py --test
python agent.py --run
```
Для Windows Service: `nssm install PrismaLitePOSAgent ...`

## 8. Лицензионный сервер

### 8.1 Установка
```
cd C:\PrismaLite\license
git clone https://repo/prismalite/license-server.git .
pip install -r requirements.txt
```

### 8.2 Конфигурация
```
LICENSE_PUBLIC_KEY=C:\PrismaLite\keys\license_public.pem
LICENSE_PRIVATE_KEY=C:\PrismaLite\keys\license_private.pem
PORT=9001
```

### 8.3 Запуск
```
python license.py
```

## 9. Проверка системы

- Backend: `curl http://localhost:8080/health/ready`
- Video: `curl http://localhost:9000/health`
- POS Agent: `python agent.py --simulate additem`
- Лицензии: `curl http://localhost:9001/status`
- UI: открыть `https://server/ui`, проверить авторизацию.

## 10. Автозапуск сервисов

Использовать NSSM для backend/video/agent/license либо PowerShell Scheduled Tasks. Проверить `services.msc`, установить `Start type = Automatic`.

## 11. Журналы и каталоги

| Сервис | Логи | Конфиги |
|--------|------|---------|
| Backend | `C:\PrismaLite\logs\backend\*.log` | `.env`, `alembic.ini` |
| Video | `C:\PrismaLite\logs\video\*.log` | `video.yaml` |
| Agent | `C:\PrismaLite\agent\logs\` | `config.yaml` |
| License | `C:\PrismaLite\logs\license\*.log` | `.env` |
| HLS | `C:\PrismaLite\hls\` | --- |

## 12. Типовые проблемы

| Симптом | Возможная причина | Решение |
|---------|------------------|---------|
| `pip install` падает | Нет VC++ libs | Установить VC++ Redistributable |
| Agent не отправляет события | Нет связи с backend | Проверить firewall/VPN, `agent.log` |
| Нет видео | FFmpeg не установлен или нет доступа к DVR | Проверить `video.log`, учётные данные |
| Ошибка БД | Неверный пароль, нет прав | Проверить `.env`, pg_hba.conf |

## 13. Обновления

1. Остановить сервис.
2. `git pull`.
3. `pip install -r requirements.txt`.
4. Миграции (backend).
5. Запустить сервис.
6. Проверить health-checkи.

## 14. Документация

- `PrismaLite_Operations.md` — эксплуатация и мониторинг.
- `PrismaLite_DevOps.md` — Docker/K8s/CI/CD.
- `PrismaLite_Test_Plan.md` — проверки после установки.

Документ обновляется с каждым релизом и обязательно сверяется с фактическими пакетами поставки.

