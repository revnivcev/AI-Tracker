import os
from typing import Optional
from pydantic import BaseModel
from dotenv import load_dotenv

# Загружаем .env файл
load_dotenv()


class Settings(BaseModel):
    # Database
    DATABASE_URL: str = "postgresql://tracker_user:tracker_password@postgres:5432/tracker_db"
    
    # Telegram
    TELEGRAM_BOT_TOKEN: str
    
    # Yandex Tracker
    YANDEX_TRACKER_TOKEN: str
    YANDEX_ORG_ID: str
    YANDEX_CLOUD_ORG_ID: Optional[str] = None
    
    # LLM Configuration
    OLLAMA_BASE_URL: str = "http://ollama:11434"
    OLLAMA_MODEL: str = "deepseek-r1:1.5b"
    
    # Sber GigaChat
    GIGACHAT_API_KEY: Optional[str] = None
    GIGACHAT_AUTH_URL: Optional[str] = "https://ngw.devices.sberbank.ru:9443/api/v2/oauth"
    
    # LLM Provider (ollama or gigachat)
    LLM_PROVIDER: str = "ollama"
    
    # Application settings
    LOG_LEVEL: str = "INFO"
    DIGEST_SCHEDULE: str = "09:00"  # Default digest time
    
    # Demo mode
    DEMO_MODE: bool = False
    
    class Config:
        env_file = ".env"
        case_sensitive = True


# Load settings from environment variables
settings = Settings(
    TELEGRAM_BOT_TOKEN=os.getenv("TELEGRAM_BOT_TOKEN", ""),
    YANDEX_TRACKER_TOKEN=os.getenv("YANDEX_TRACKER_TOKEN", ""),
    YANDEX_ORG_ID=os.getenv("YANDEX_ORG_ID", ""),
    YANDEX_CLOUD_ORG_ID=os.getenv("YANDEX_CLOUD_ORG_ID"),
    DATABASE_URL=os.getenv("DATABASE_URL", "postgresql://tracker_user:tracker_password@postgres:5432/tracker_db"),
    OLLAMA_BASE_URL=os.getenv("OLLAMA_BASE_URL", "http://ollama:11434"),
    OLLAMA_MODEL=os.getenv("OLLAMA_MODEL", "deepseek-r1:1.5b"),
    GIGACHAT_API_KEY=os.getenv("GIGACHAT_API_KEY"),
    GIGACHAT_AUTH_URL=os.getenv("GIGACHAT_AUTH_URL", "https://ngw.devices.sberbank.ru:9443/api/v2/oauth"),
    LLM_PROVIDER=os.getenv("LLM_PROVIDER", "ollama"),
    LOG_LEVEL=os.getenv("LOG_LEVEL", "INFO"),
    DIGEST_SCHEDULE=os.getenv("DIGEST_SCHEDULE", "09:00"),
    DEMO_MODE=os.getenv("DEMO_MODE", "false").lower() == "true"
)

# Check if we're in demo mode
if settings.DEMO_MODE:
    print("🚀 Запуск в ДЕМО-режиме!")
    print("Для полноценной работы настройте API ключи в файле .env") 