#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "📦 Создаю структуру backend PrismaLite…"
cd "$ROOT_DIR"

# ---------------------------
#  Папки backend
# ---------------------------
mkdir -p backend/app/api
mkdir -p backend/app/db
mkdir -p backend/app/core

echo "📁 Папки backend созданы: backend/app/api backend/app/db backend/app/core"

# ---------------------------
#  Файлы backend
# ---------------------------

create_file() {
  local path="$1"
  local content="$2"

  if [[ ! -f "$path" ]]; then
    echo "📝 Создаю файл: $path"
    echo "$content" > "$path"
  else
    echo "➡️ Пропускаю (уже есть): $path"
  fi
}

# main.py
create_file backend/app/main.py \
"from fastapi import FastAPI

app = FastAPI(title='PrismaLite Backend')

from app.api.events import router as events_router
app.include_router(events_router, prefix='/api/v1/events')

@app.get('/')
def root():
    return { 'status': 'ok', 'message': 'PrismaLite backend is running' }"

# events.py
create_file backend/app/api/events.py \
"from fastapi import APIRouter
from fastapi import HTTPException
from typing import List, Dict, Any

router = APIRouter()

@router.post('/ingest')
async def ingest_events(data: Dict[str, Any]):
    # временный ответ, позже добавим запись в БД
    return { 'status': 'ok', 'received': data }"

# connection.py
create_file backend/app/db/connection.py \
"import psycopg2
import os

def get_connection():
    return psycopg2.connect(
        dbname=os.getenv('DB_NAME', 'prismalite'),
        user=os.getenv('DB_USER', 'prismalite'),
        password=os.getenv('DB_PASSWORD', 'prismalite'),
        host=os.getenv('DB_HOST', 'localhost'),
        port=os.getenv('DB_PORT', '5432')
    )"

# models.py
create_file backend/app/db/models.py \
"# Модели БД появятся позже"

# config.py
create_file backend/app/core/config.py \
"DB_NAME='prismalite'
DB_USER='prismalite'
DB_PASSWORD='prismalite'
DB_HOST='localhost'
DB_PORT=5432"

# requirements.txt
create_file backend/requirements.txt \
"fastapi
uvicorn
psycopg2-binary
pydantic
python-dotenv"

# ---------------------------
# EDR Format
# ---------------------------
mkdir -p docs/backend

create_file docs/backend/EDR_Format.md \
\"# EDR Format
Документация будет добавлена позже. Это заглушка.
\"

echo "✅ Backend структура успешно создана!"
