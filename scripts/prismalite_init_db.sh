#!/usr/bin/env bash
set -euo pipefail

# Настройки БД (можешь поменять под себя)
DB_NAME="prismalite"
DB_USER="prismalite"
DB_PASSWORD="prismalite"
DB_HOST="localhost"
DB_PORT="5432"

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SCHEMA_FILE="$ROOT_DIR/docs/db/PrismaLite_DB_Schema.sql"

echo "📦 Инициализация PostgreSQL для PrismaLite"
echo "  DB:   $DB_NAME"
echo "  USER: $DB_USER"
echo "  HOST: $DB_HOST:$DB_PORT"
echo "  SCHEMA FILE: $SCHEMA_FILE"
echo

if ! command -v psql >/dev/null 2>&1; then
  echo "❌ psql не найден. Установи PostgreSQL client (psql) и повтори."
  exit 1
fi

# =========================
# 1. Создаём пользователя
# =========================
echo "👤 Создаю пользователя (если ещё нет)..."
# Проверяем, есть ли уже роль
psql -h "$DB_HOST" -p "$DB_PORT" -U postgres -v ON_ERROR_STOP=1 -tAc \
  "SELECT 1 FROM pg_roles WHERE rolname = '$DB_USER';" | grep -q 1 || \
psql -h "$DB_HOST" -p "$DB_PORT" -U postgres -v ON_ERROR_STOP=1 -c \
  "CREATE ROLE $DB_USER LOGIN PASSWORD '$DB_PASSWORD';"

# =========================
# 2. Создаём БД
# =========================
echo "🗄  Создаю БД (если ещё нет)..."
DB_EXISTS=$(psql -h "$DB_HOST" -p "$DB_PORT" -U postgres -tAc \
  "SELECT 1 FROM pg_database WHERE datname = '$DB_NAME';" || echo "")

if [[ "$DB_EXISTS" != "1" ]]; then
  psql -h "$DB_HOST" -p "$DB_PORT" -U postgres -v ON_ERROR_STOP=1 -c \
    "CREATE DATABASE $DB_NAME OWNER $DB_USER;"
else
  echo "➡️  БД $DB_NAME уже существует, пропускаю создание."
fi

# =========================
# 3. Применяем схему
# =========================
if [ ! -f "$SCHEMA_FILE" ]; then
  echo "❌ Не найден файл схемы: $SCHEMA_FILE"
  exit 1
fi

echo "📜 Применяю схему..."
PGPASSWORD="$DB_PASSWORD" psql \
  -h "$DB_HOST" -p "$DB_PORT" \
  -U "$DB_USER" -d "$DB_NAME" \
  -v ON_ERROR_STOP=1 \
  -f "$SCHEMA_FILE"

echo "✅ Готово. БД $DB_NAME инициализирована."
