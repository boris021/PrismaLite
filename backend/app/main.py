from fastapi import FastAPI

from app.api.events import router as events_router

app = FastAPI(title="PrismaLite Backend")

app.include_router(events_router, prefix="/api/v1")

@app.get("/")
def root():
    return {"status": "ok", "message": "PrismaLite backend is running"}
