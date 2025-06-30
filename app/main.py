import asyncio
import logging
import sys
import time
from app.config import settings
from app.models.database import engine, Base
from app.telegram.bot import TelegramBot
from app.scheduler.digest_scheduler import DigestScheduler

# Настройка логирования
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/app.log'),
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)


def init_database():
    """Инициализация базы данных"""
    try:
        # Создаем таблицы
        Base.metadata.create_all(bind=engine)
        logger.info("База данных инициализирована")
    except Exception as e:
        logger.error(f"Ошибка при инициализации базы данных: {e}")
        raise


def main():
    """Главная функция приложения"""
    try:
        logger.info("Запуск AI-Tracker...")
        
        # Инициализируем базу данных
        init_database()
        
        # Создаем и запускаем Telegram бота
        bot = TelegramBot()
        
        # Создаем планировщик
        scheduler = DigestScheduler(bot)
        bot.scheduler = scheduler
        
        # Запускаем планировщик
        scheduler.start()
        
        logger.info("AI-Tracker запущен успешно")
        
        if settings.DEMO_MODE:
            # В демо-режиме просто держим приложение запущенным
            logger.info("🔄 Демо-режим: приложение работает в фоне")
            while True:
                time.sleep(60)  # Проверяем каждую минуту
        else:
            # Запускаем бота (блокирующий вызов)
            bot.run_polling()
        
    except KeyboardInterrupt:
        logger.info("Получен сигнал остановки...")
    except Exception as e:
        logger.error(f"Критическая ошибка: {e}")
        sys.exit(1)
    finally:
        logger.info("AI-Tracker остановлен")


if __name__ == "__main__":
    main() 