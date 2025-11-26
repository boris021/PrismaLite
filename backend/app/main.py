import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.api.events import router as events_router
from app.api.receipts import router as receipts_router
from app.api.setretail import router as setretail_router
from app.api.incidents import router as incidents_router
from app.api import receipts, incidents, ui_incidents

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("prismalite")

# === БАЗОВЫЙ КАТАЛОГ app ===
# => D:\PrismaLite\backend\app
BASE_DIR = Path(__file__).resolve().parent

# === ПАПКА UI ДЛЯ ИНЦИДЕНТОВ ===
# => D:\PrismaLite\backend\app\ui\incidents
UI_INCIDENTS_DIR = BASE_DIR / "ui" / "incidents"

app = FastAPI(title="PrismaLite Backend")

# === СТАТИКА ДЛЯ UI (CSS/JS), КОРЕНЬ = ui/incidents ===
app.mount(
    "/static",
    StaticFiles(directory=str(UI_INCIDENTS_DIR)),
    name="static",
)

# === API v1 ===
app.include_router(events_router, prefix="/api/v1")
app.include_router(receipts_router, prefix="/api/v1")
app.include_router(incidents_router, prefix="/api/v1")
app.include_router(receipts.router, prefix="/api/v1")
app.include_router(incidents.router, prefix="/api/v1")

# UI роутер (страница /ui/incidents)
app.include_router(ui_incidents.router)

# SetRetail integration
app.include_router(setretail_router, prefix="/api/v1")


@app.get("/")
def root():
    return {"status": "ok", "message": "PrismaLite backend is running"}
