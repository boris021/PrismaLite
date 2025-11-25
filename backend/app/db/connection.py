import os
import psycopg2
from psycopg2.extras import Json


DB_NAME = os.getenv("DB_NAME", "prismalite")
DB_USER = os.getenv("DB_USER", "prismalite")
DB_PASSWORD = os.getenv("DB_PASSWORD", "prismalite")
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("DB_PORT", "5432"))


def get_connection():
    """
    Открывает синхронное подключение к PostgreSQL.
    Для простоты пока без пула соединений.
    """
    conn = psycopg2.connect(
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
        host=DB_HOST,
        port=DB_PORT,
    )
    return conn


def jsonb(value):
    """
    Обёртка для безопасной вставки JSONB.
    """
    if value is None:
        return None
    return Json(value)
