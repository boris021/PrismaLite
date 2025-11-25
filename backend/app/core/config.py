# backend/app/core/config.py
from pydantic import BaseSettings


class SetRetailConfig(BaseSettings):
    """
    Настройки подключения к SOAP-сервису SetRetail.
    """
    host: str = "192.168.50.90"       # IP сервера SetRetail
    port: int = 8090                  # порт ERPIntegration
    path: str = "/SET-ERPIntegration/FiscalInfoExport"
    request_timeout_sec: int = 10     # таймаут SOAP-запросов

    class Config:
        env_prefix = "PRISMALITE_SETRETAIL_"
        env_file = ".env"


class AppConfig(BaseSettings):
    """
    Общие настройки приложения PrismaLite.
    При необходимости сюда добавим БД, JWT и т.д.
    """
    setretail: SetRetailConfig = SetRetailConfig()

    class Config:
        env_file = ".env"


settings = AppConfig()
