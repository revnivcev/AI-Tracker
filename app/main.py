"""
Основной модуль приложения
"""

import asyncio
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.infrastructure.database.models import engine, Base
from app.telegram.bot import TelegramBot
from app.scheduler.digest_scheduler import DigestScheduler
from app.services.llm_service import LLMService
from app.services.tracker_service import TrackerService

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def check_ollama_model():
    """Проверить доступность модели Ollama при запуске"""
    try:
        logger.info("🔍 Проверяю доступность модели Ollama...")
        
        llm_service = LLMService()
        health_status = await llm_service.health_check()
        
        ollama_status = health_status.get('ollama', {})
        if ollama_status.get('healthy', {}).get('status') == 'healthy':
            model_available = ollama_status.get('healthy', {}).get('model_available', False)
            if model_available:
                logger.info(f"✅ Модель {settings.OLLAMA_MODEL} доступна и готова к работе!")
                return True
            else:
                logger.error(f"❌ Модель {settings.OLLAMA_MODEL} не найдена в Ollama!")
                logger.error("Для установки модели выполните: ollama pull deepseek-r1:1.5b")
                return False
        else:
            logger.error("❌ Ollama недоступен или не отвечает!")
            return False
            
    except Exception as e:
        logger.error(f"❌ Ошибка при проверке модели Ollama: {e}")
        return False


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Управление жизненным циклом приложения"""
    # Создаем таблицы при запуске
    logger.info("🗄️ Создаю таблицы базы данных...")
    Base.metadata.create_all(bind=engine)
    
    # Проверяем модель Ollama
    model_available = await check_ollama_model()
    if not model_available:
        logger.warning("⚠️ Модель Ollama недоступна! Некоторые функции могут не работать.")
    
    # Инициализируем сервисы
    logger.info("🚀 Инициализирую сервисы...")
    
    # Создаем экземпляры сервисов
    tracker_service = TrackerService(
        token=settings.YANDEX_TRACKER_TOKEN,
        org_id=settings.YANDEX_ORG_ID
    )
    llm_service = LLMService()
    
    # Инициализируем Telegram бота
    bot = TelegramBot()
    
    # Инициализируем планировщик
    scheduler = DigestScheduler(bot)
    scheduler.start()
    
    # Сохраняем в app.state для доступа из других частей
    app.state.tracker_service = tracker_service
    app.state.llm_service = llm_service
    app.state.scheduler = scheduler
    app.state.bot = bot
    
    logger.info("✅ Приложение успешно запущено!")
    
    yield
    
    # Очистка при завершении
    logger.info("🛑 Останавливаю приложение...")
    await scheduler.stop()
    logger.info("✅ Приложение остановлено.")


# Создаем FastAPI приложение
app = FastAPI(
    title="AI-Tracker API",
    description="API для работы с Yandex Tracker через AI",
    version="2.0.0",
    lifespan=lifespan
)

# Добавляем CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    """Корневой эндпоинт"""
    return {
        "message": "AI-Tracker API",
        "version": "2.0.0",
        "status": "running"
    }


@app.get("/health")
async def health_check():
    """Проверка здоровья сервиса"""
    try:
        # Проверяем доступность сервисов
        llm_service = app.state.llm_service
        health_status = await llm_service.health_check()
        
        return {
            "status": "healthy",
            "services": {
                "llm": health_status,
                "database": "connected",
                "scheduler": "running"
            }
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise HTTPException(status_code=500, detail="Service unhealthy")


@app.get("/model/status")
async def model_status():
    """Статус модели LLM"""
    try:
        llm_service = app.state.llm_service
        health_status = await llm_service.health_check()
        
        return {
            "model": settings.OLLAMA_MODEL,
            "provider": settings.LLM_PROVIDER,
            "status": health_status
        }
    except Exception as e:
        logger.error(f"Model status check failed: {e}")
        raise HTTPException(status_code=500, detail="Model status check failed")


if __name__ == "__main__":
    import uvicorn
    
    logger.info("🚀 Запуск AI-Tracker...")
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    ) 