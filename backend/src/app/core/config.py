from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "PrismaLite Backend"
    debug: bool = False
    database_url: str = "postgresql+asyncpg://prismlite:prismlite@localhost:5432/prismlite"

    class Config:
        env_prefix = "PRISMALITE_"
        env_file = ".env"


settings = Settings()

