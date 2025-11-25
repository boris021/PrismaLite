#!/usr/bin/env bash

# Быстрый вход в базу PrismaLite
# Работает из Git Bash под Windows

DB_NAME="prismalite"
DB_USER="prismalite"
DB_HOST="localhost"
DB_PORT="5432"
DB_PASS="prismalite"

export PGPASSWORD="$DB_PASS"

echo "🚀 Подключаюсь к PostgreSQL → база: $DB_NAME"
psql -U "$DB_USER" -d "$DB_NAME" -h "$DB_HOST" -p "$DB_PORT"
