# PrismaLite_DevOps

Документ описывает процессы DevOps: контейнеризация, Kubernetes, CI/CD, мониторинг, логирование, бэкапы, Production практики и нагрузочные стенды.

## 1. Docker / Docker Compose

### 1.1 Сервисы
- `backend`: FastAPI, порт 8080.
- `agent`: POS Agent.
- `video`: Video Proxy.
- `license`: License server.
- `db`: PostgreSQL 14 (локально, для разработки).
- `prometheus`, `grafana`, `loki`, `promtail` (опционально).

### 1.2 docker-compose.yml (фрагмент)
```yaml
version: "3.9"
services:
  db:
    image: postgres:14
    environment:
      POSTGRES_DB: prismlite
      POSTGRES_USER: prismlite
      POSTGRES_PASSWORD: change_me
    volumes:
      - db_data:/var/lib/postgresql/data
    restart: unless-stopped

  backend:
    build: ../backend
    env_file:
      - ../backend/.env
    depends_on: [db, license, video]
    ports: ["8080:8080"]
    restart: unless-stopped

  video:
    build: ../video
    ports: ["9000:9000"]

volumes:
  db_data: {}
```

### 1.3 Dockerfiles
- `infra/docker/backend.dockerfile`: многоэтапная сборка (poetry/requirements → runtime).
- `infra/docker/video.dockerfile`: включает ffmpeg.
- `infra/docker/agent.dockerfile`.

## 2. Kubernetes

### 2.1 Компоненты
- Namespaces: `prismalite-dev`, `prismalite-prod`.
- Deployments: backend, video, agent (optional daemonset), license.
- Services (ClusterIP), Ingress (nginx/traefik), Secrets, ConfigMaps.

### 2.2 Пример backend Deployment
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: prismlite-backend
spec:
  replicas: 3
  selector:
    matchLabels:
      app: prismlite-backend
  template:
    metadata:
      labels:
        app: prismlite-backend
    spec:
      containers:
        - name: backend
          image: registry/prismalite/backend:{{ .Values.imageTag }}
          envFrom:
            - secretRef:
                name: prismlite-backend-secrets
          ports:
            - containerPort: 8080
          readinessProbe:
            httpGet:
              path: /health/ready
              port: 8080
          livenessProbe:
            httpGet:
              path: /health/live
              port: 8080
          resources:
            requests:
              cpu: "250m"
              memory: "512Mi"
            limits:
              cpu: "1"
              memory: "1Gi"
```

### 2.3 Secrets
- Использовать K8s Secrets/SealedSecrets или HashiCorp Vault.
- Секреты: DB credentials, JWT keys, DVR credentials, license keys.

### 2.4 Autoscaling
```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: prismlite-backend-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: prismlite-backend
  minReplicas: 2
  maxReplicas: 10
  metrics:
    - type: Resource
      resource:
        name: cpu
        target:
          type: Utilization
          averageUtilization: 70
```

## 3. CI/CD

### 3.1 GitHub Actions (пример)
`.github/workflows/backend-ci.yml`
```yaml
name: Backend CI
on:
  push:
    paths:
      - "backend/**"
  pull_request:
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - run: pip install -r backend/requirements.txt
      - run: pytest backend/tests
  build:
    needs: test
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: docker build -f infra/docker/backend.dockerfile -t registry/prismalite/backend:${{ github.sha }} .
      - run: docker push registry/prismalite/backend:${{ github.sha }}
```

### 3.2 GitLab CI
`.gitlab-ci.yml` с этапами `lint → test → build → deploy`.

### 3.3 Deploy
- Helm charts или Kustomize.
- CD: ArgoCD / Flux / GitOps pipeline.
- Prod deploy — progressive (canary/blue-green).

## 4. Мониторинг и логирование

### 4.1 Prometheus + Grafana
- Backend: HTTP latency, events/sec, rules latency, DB pool usage.
- Video: RTSP sessions, HLS segment latency, DVR errors.
- POS Agent: buffered events, send failures.
- PostgreSQL exporter.
- Grafana dashboards (per component).

### 4.2 Loki / ELK
- Все сервисы логируют в stdout (JSON).
- Promtail/Fluent Bit собирают и отправляют в Loki/Elastic.
- Ретенция: 14–30 дней (application), 180 дней (audit).

### 4.3 Alertmanager
- Правила: response time, ingest gaps, DVR overload, db disk usage, license expiry.
- Интеграции: Slack/Teams/email.

## 5. Бэкапы

- PostgreSQL: daily full backup, WAL archiving, test restore ежеквартально.
- Видео: ротация, выгрузка на S3/Glacier, проверка целостности.
- Config/Secrets: зашифрованные backup (Vault, SOPS).
- CI: автоматическое создание snapshot перед major релизами.

## 6. Production рекомендации

- Разделять среды: DEV, STAGE, PROD.
- В PROD минимум 2 реплики backend + Video Proxy, DB с репликой (streaming replication), отдельное хранилище для видео.
- Обязателен мониторинг, централизованные логи, alerting.
- Лицензионный сервер резервировать (active/passive).
- Нагрузка: рассчитывать ресурсы на 1 млн событий/сутки, 20+ live потоков.
- Security: TLS everywhere, VPN для DVR.

## 7. Нагрузочные стенды

- **Event Storm**: скрипт `scripts/stress_test_events.py` генерирует 300–500 events/sec.
- **Video Storm**: ffmpeg-генераторы RTSP → Video Proxy, 20 операторов × 4 камеры.
- **Combined Test**: одновременно Event + Video Storm.
- **Failover**: отключение узлов (backend pod, video service, DB) с проверкой восстановления.
- Инструменты: Locust/k6 для API, custom RTSP load generator.

## 8. Обновления и откаты

- Использовать миграции БД (Alembic) с возможностью downgrade.
- Docker images тегировать `git-sha` + `semver`.
- Для критических фиксов — hotfix branch.
- Откат: `helm rollback`, `kubectl rollout undo`, restore DB backup (при необходимости).

## 9. Observability и SRE

- SLO: 99.5% uptime API, 99% Video live availability.
- Error budget: 0.5% downtime/месяц.
- Инциденты: постмортем в Confluence/Notion, action items.
- Synthetic monitoring: cron job проверяет ingest → video → UI.

## 10. Документы/ссылки

- `PrismaLite_Installation.md` — standalone установка.
- `PrismaLite_Operations.md` — эксплуатация и мониторинг.
- `PrismaLite_Test_Plan.md` — тестирование.
- Helm/terraform репозитории (если вынесены).

Документ обновляется при изменении инфраструктуры, CI/CD, мониторинга и политик эксплуатации.

