# PrismaLite_Repository_Structure

## 1. Принципы

- Единая monorepo структура для backend, агентa, видеомодуля, документации и инфраструктуры.
- Код разделён по доменам; общие компоненты оформлены как пакеты/библиотеки.
- Поддержка GitHub/GitLab, CI/CD, Docker/Kubernetes.

## 2. Дерево

```
/
├── backend/
├── agent/
├── video/
├── docs/
├── infra/
├── deploy/
└── scripts/
```

## 3. backend/

```
backend/
├── src/
│   ├── api/
│   ├── core/
│   ├── db/
│   ├── security/
│   ├── services/
│   ├── rules/
│   ├── video/
│   └── utils/
├── migrations/
├── tests/
├── requirements.txt
├── pyproject.toml / setup.cfg
├── settings.example.env
└── README.md
```

- `src/api` — REST/WebSocket endpoints (FastAPI).
- `src/services` — бизнес-логика.
- `src/rules` — Rules Engine.
- `src/video` — интеграция с видеомодулем.
- `migrations` — Alembic.
- `tests` — pytest (unit + integration).
- `.env` пример с описанием переменных.

## 4. agent/

```
agent/
├── src/
│   ├── setretail/
│   ├── frontol/
│   ├── buffer/
│   ├── sender/
│   └── utils/
├── config/
│   └── config.example.yaml
├── install/
│   ├── windows-service.nssm
│   ├── installer.ps1
│   └── installer.sh
├── logs/
├── tests/
├── requirements.txt
└── README.md
```

- `buffer/` — offline очередь.
- `sender/` — доставка событий в backend (HTTP/gRPC).
- `install/` — скрипты развертывания (Windows/Linux).

## 5. video/

```
video/
├── src/
│   ├── drivers/
│   │   ├── hikvision.py
│   │   ├── dahua.py
│   │   └── csi.py
│   ├── proxy/
│   ├── hls/
│   └── utils/
├── config/
│   └── video.example.yaml
├── logs/
├── tests/
├── requirements.txt
└── README.md
```

- `drivers/` — DVR адаптеры.
- `proxy/` — RTSP→HLS сервис.
- `hls/` — генерация плейлистов, токенов.

## 6. docs/

Содержит всю документацию:
- `PrismaLite_Master_Document.md`
- `PrismaLite_Functional_Spec.md`
- `PrismaLite_Technical_Spec.md`
- `PrismaLite_Security.md`
- `PrismaLite_Video_Module.md`
- `PrismaLite_Integrations.md`
- `PrismaLite_Rules_and_Incidents.md`
- `PrismaLite_Database_Design.md`
- `PrismaLite_DB_Schema.sql`
- `PrismaLite_Installation.md`
- `PrismaLite_Operations.md`
- `PrismaLite_Development_Roadmap.md`
- `PrismaLite_Repository_Structure.md`
- `PrismaLite_API_Reference.md`
- `PrismaLite_UI_Guide.md`
- `PrismaLite_DevOps.md`
- `PrismaLite_Test_Plan.md`

Дополнительно: `CHANGELOG.md`, `README.md`, схемы.

## 7. infra/

```
infra/
├── docker/
│   ├── backend.dockerfile
│   ├── agent.dockerfile
│   ├── video.dockerfile
│   └── docker-compose.yml
├── k8s/
│   ├── backend.yaml
│   ├── agent.yaml
│   ├── video.yaml
│   ├── license.yaml
│   ├── ingress.yaml
│   └── secrets.example.yaml
└── README.md
```

- Dockerfiles для сервисов.
- `docker-compose` для локального/стендового развертывания.
- K8s манифесты (Deployment, Service, Ingress, HPA, Secrets).

## 8. deploy/

```
deploy/
├── ansible/
│   ├── backend.yml
│   ├── agent.yml
│   └── video.yml
├── windows/
│   ├── install_backend.ps1
│   ├── install_agent.ps1
│   └── install_video.ps1
├── linux/
│   ├── install_backend.sh
│   ├── install_agent.sh
│   └── install_video.sh
└── README.md
```

- Скрипты для автоматизации развертываний (Ansible, PowerShell, Bash).

## 9. scripts/

```
scripts/
├── test_ingest.py
├── stress_test_events.py
├── test_video_stream.py
├── migrate_db.py
├── backup_db.ps1
└── README.md
```

- Утилиты для тестирования, миграций, резервного копирования.

## 10. Дополнительно

- `.github/` или `.gitlab-ci.yml` — CI/CD pipeline (lint/test/build/deploy).
- `Makefile` / `justfile` — типовые команды (`make lint`, `make test`).
- `.editorconfig`, `.pre-commit-config.yaml` — единый стиль.
- `LICENSE`, `CONTRIBUTING.md`.

Документ обновляется при изменении структуры репозитория и добавлении новых модулей.

