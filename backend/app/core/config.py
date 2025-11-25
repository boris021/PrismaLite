from pydantic import BaseSettings, AnyHttpUrl


class SetRetailConfig(BaseSettings):
    # IP сервера SetRetail (тот где крутится SOAP ERPIntegration)
    host: str = "192.168.50.90"

    # Порт ERPIntegration (по документации 8090)
    port: int = 8090

    # Относительный путь сервиса
    # В документации: /SET-ERPIntegration/FiscalInfoExport
    path: str = "/SET-ERPIntegration/FiscalInfoExport"

    # Таймауты
    request_timeout_sec: int = 10

    class Config:
        env_prefix = "PRISMALITE_SETRETAIL_"
        env_file = ".env"


class AppConfig(BaseSettings):
    setretail: SetRetailConfig = SetRetailConfig()

    class Config:
        env_file = ".env"


settings = AppConfig()
