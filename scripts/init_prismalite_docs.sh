#!/usr/bin/env bash
set -euo pipefail

# Скрипт запускается из любой директории внутри репо, сам находит корень
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "📚 PrismaLite docs init"
echo "Root: $ROOT_DIR"

# 1. Базовые каталоги документации
DOCS_DIR="$ROOT_DIR/docs"

mkdir -p "$DOCS_DIR"/{architecture,db,devops,modules,operations,testing,ui}

echo "✅ Created/verified docs subdirs:
  - architecture
  - db
  - devops
  - modules
  - operations
  - testing
  - ui
"

# Вспомогательная функция: создать файл, если его нет
create_if_missing() {
  local path="$1"
  local content="$2"

  if [ -f "$path" ]; then
    echo "➡️  Skip (exists): $path"
  else
    echo "✏️  Create: $path"
    mkdir -p "$(dirname "$path")"
    cat > "$path" << 'EOF'
'"$content"'
EOF
  fi
}

########################################
# 2. README по структуре docs
########################################
create_if_missing "$DOCS_DIR/README.md" "# PrismaLite docs

Эта папка содержит документацию проекта PrismaLite.

## Структура

- \`PrismaLite_Master_Document.md\` — основной обзорный документ (визия + модули).
- \`architecture/\` — общая архитектура, схемы, формат интеграций.
- \`db/\` — схема БД, миграции, тестовые данные.
- \`devops/\` — деплой, Docker/Docker Compose, Kubernetes, CI/CD, мониторинг, бэкапы.
- \`modules/\` — описания модулей (agent, backend, video, правила, инциденты).
- \`operations/\` — инструкции эксплуатации (runbook, гайды для СБ).
- \`testing/\` — тест-план и чек-листы.
- \`ui/\` — гайд по интерфейсу, роли и права.

"

########################################
# 3. Master document (каркас)
########################################
create_if_missing "$DOCS_DIR/PrismaLite_Master_Document.md" "# PrismaLite — мастер-документ

## 1. Введение
- Назначение системы
- Краткое сравнение с SET Prisma
- Термины и определения

## 2. Визия и цели
- Для кого делаем (служба безопасности, руководство)
- Какие задачи закрываем в первой версии (MVP)
- Ограничения и допущения

## 3. Архитектура (обзор)
- Основные компоненты: agent, backend, video, UI, БД
- Поток данных: чек → события → видео → инцидент
- Интеграции с внешними системами

## 4. Модули (обзор)
- Agent (ingest POS/логов)
- Backend (API + бизнес-логика)
- Video (поиск и выдача видеосегментов)
- UI (аналитика, инциденты, отчёты)

## 5. Нефункциональные требования
- Производительность
- Надёжность
- Безопасность и аудит

## 6. Документация
- Структура \`docs/\`
- Где искать dev/ops-инфу
- Как обновлять этот документ

"

########################################
# 4. DevOps-документация (каркас)
########################################
create_if_missing "$DOCS_DIR/devops/PrismaLite_DevOps.md" "# PrismaLite DevOps Guide

## 1. Обзор инфраструктуры
- Окружения: dev, staging, prod
- Стек: Docker/Docker Compose, опционально Kubernetes

## 2. Docker / Docker Compose
- Образ backend
- Образ agent
- Образ video-модуля
- Образ PostgreSQL
- Базовый \`docker-compose.yml\` (описание сервисов, сети, volumes)

## 3. Kubernetes (опционально, позже)
- Deployment для backend/agent/video
- Service + Ingress
- ConfigMap / Secrets
- Autoscaling

## 4. CI/CD (GitHub Actions / GitLab CI)
- Pipelines:
  - Линтеры и тесты
  - Сборка и пуш Docker-образов
  - Деплой на staging/prod

## 5. Мониторинг и логирование
- Стек: Prometheus, Loki, Grafana
- Метрики для backend, agent, video
- Ретенция логов и метрик

## 6. Бэкапы
- Бэкап БД (PostgreSQL)
- Бэкап конфигов и секретов
- Проверка восстановления

## 7. Production-рекомендации
- Ресурсы (CPU/RAM/Storage)
- Настройки таймаутов
- Политики обновлений

"

########################################
# 5. Test Plan (каркас)
########################################
create_if_missing "$DOCS_DIR/testing/PrismaLite_Test_Plan.md" "# PrismaLite Test Plan

## 1. Область тестирования
- Какие модули входят в тест-план
- Что не входит (out of scope)

## 2. Типы тестов
- Unit-тесты backend
- Интеграционные тесты
- E2E-сценарии (чек → события → видео → инцидент)
- Регрессионные тесты
- Нагрузочные тесты
- Security-тесты (JWT, ACL, tenants)

## 3. POS ingest tests
- Тестовые наборы чеков
- Валидация формата
- Обработка ошибок

## 4. Video module tests
- Проверка получения видеосегментов
- Проверка маппинга касса → камера
- Обработка недоступности регистратора

## 5. Критерии приёмки
- Условия, когда фича считается готовой
- Порог по покрытиям тестами (если нужен)

"

########################################
# 6. Схема БД (заглушка)
########################################
create_if_missing "$DOCS_DIR/db/PrismaLite_DB_Schema.sql" "-- PrismaLite DB Schema
-- TODO: сюда переносим реальную SQL-схему (CREATE TABLE ...),
-- включая PK/FK, индексы, partitioning, триггеры и проверки целостности.

-- Стартовая структура будет описана отдельной миграцией:
-- 0001_initial.sql, 0002_events.sql, 0003_video.sql, 0004_incidents.sql, и т.д.

"

echo "✅ Done. Docs skeleton is ready."
