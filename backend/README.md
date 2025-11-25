# PrismaLite Backend

Минимальный каркас FastAPI приложения.

## Запуск

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate  # Windows
pip install -r requirements.txt
alembic upgrade head  # создаст таблицы
uvicorn app.main:app --reload --app-dir src
```

Переменные окружения задаются через `.env` (см. `.env.example`).

