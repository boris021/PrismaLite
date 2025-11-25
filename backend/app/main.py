from fastapi import FastAPI

from app.api.events import router as events_router
from app.api.receipts import router as receipts_router

app = FastAPI(title="PrismaLite Backend")

app.include_router(events_router, prefix="/api/v1")
app.include_router(receipts_router, prefix="/api/v1")


@app.get("/")
def root():
    return {"status": "ok", "message": "PrismaLite backend is running"}
