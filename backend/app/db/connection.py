import os
import psycopg2
from psycopg2.extras import Json


DB_NAME = os.getenv("DB_NAME", "prismalite")
DB_USER = os.getenv("DB_USER", "prismalite")
DB_PASSWORD = os.getenv("DB_PASSWORD", "prismalite")
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("DB_PORT", "5432"))


def get_connection():
    conn = psycopg2.connect(
        host=os.getenv("DB_HOST", "localhost"),
        port=int(os.getenv("DB_PORT", "5432")),
        dbname=os.getenv("DB_NAME", "prismalite"),
        user=os.getenv("DB_USER", "postgres"),      # ← БЫЛО "prismalite"
        password=os.getenv("DB_PASSWORD", "postgres"),  # ← Поставь свой реальный пароль
    )
    conn.autocommit = True
    return conn


def jsonb(value):
    """
    Обёртка для безопасной вставки JSONB.
    """
    if value is None:
        return None
    return Json(value)
