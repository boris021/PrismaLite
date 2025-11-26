import logging
from fastapi import FastAPI

from app.api.events import router as events_router
from app.api.receipts import router as receipts_router
from app.api.setretail import router as setretail_router
from app.api.incidents import router as incidents_router  # ← ДОБАВИЛИ

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("prismalite")

app = FastAPI(title="PrismaLite Backend")

# API v1
app.include_router(events_router, prefix="/api/v1")
app.include_router(receipts_router, prefix="/api/v1")
app.include_router(incidents_router, prefix="/api/v1")  # ← ДОБАВИЛИ

# SetRetail integration
app.include_router(setretail_router, prefix="/api/v1")

@app.get("/")
def root():
    return {"status": "ok", "message": "PrismaLite backend is running"}
