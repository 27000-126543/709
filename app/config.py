from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    APP_NAME: str = "全国器官捐献与移植协调调度平台"
    DATABASE_URL: str = "sqlite+aiosqlite:///./organ_transplant.db"
    SECRET_KEY: str = "your-secret-key-change-in-production"
    APPROVAL_TIMEOUT_HOURS: int = 2
    CONSUMABLE_SAFETY_STOCK: int = 10
    TRANSPORT_TEMP_MIN: float = 2.0
    TRANSPORT_TEMP_MAX: float = 8.0
    TRANSPORT_MAX_DEVIATION_KM: float = 10.0
    MATCH_BLOOD_TYPE_WEIGHT: float = 0.3
    MATCH_HLA_WEIGHT: float = 0.3
    MATCH_PRA_WEIGHT: float = 0.15
    MATCH_GEOGRAPHY_WEIGHT: float = 0.1
    MATCH_URGENCY_WEIGHT: float = 0.15
    REPORT_CRON_HOUR: int = 0

    class Config:
        env_file = ".env"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
