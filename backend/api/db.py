# backend/api/db.py

import psycopg2
from psycopg2.extras import RealDictCursor
from contextlib import contextmanager

# ВАЖНО: пароль и параметры те же, что в event_engine.py / incident_engine.py
DB_CONFIG = {
    "host": "localhost",
    "dbname": "prismalite",
    "user": "postgres",
    "password": "postgres",  # ← поменяй на свой реальный пароль
}


@contextmanager
def get_conn():
    conn = psycopg2.connect(cursor_factory=RealDictCursor, **DB_CONFIG)
    try:
        yield conn
    finally:
        conn.close()
