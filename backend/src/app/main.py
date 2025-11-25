from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncEngine

from .api.router import api_router
from .core.config import settings
from .core.database import engine
from .db.base import Base


def create_app(db_engine: AsyncEngine = engine) -> FastAPI:
    """Application factory."""
    app = FastAPI(
        title="PrismaLite Backend",
        version="0.1.0",
        description="Core API for PrismaLite platform",
    )

    @app.get("/health/live", tags=["health"])
    async def health_live() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/health/ready", tags=["health"])
    async def health_ready() -> dict[str, str]:
        return {"status": "ok"}

    @app.on_event("startup")
    async def startup() -> None:
        async with db_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    app.include_router(api_router, prefix="/api/v1")
    return app


app = create_app()

