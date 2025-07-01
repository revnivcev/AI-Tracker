#!/usr/bin/env python3
"""
Отдельный entrypoint для Telegram-бота
Запускает только polling без FastAPI
"""

import logging
import sys
import os

# Добавляем путь к app в sys.path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

from app.tg_bot.bot import TelegramBot

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def main():
    """Главная функция для запуска Telegram-бота"""
    try:
        logger.info("🤖 Запуск Telegram-бота...")
        bot = TelegramBot()
        logger.info("✅ Telegram-бот инициализирован, запускаю polling...")
        bot.run_polling()
    except KeyboardInterrupt:
        logger.info("🛑 Telegram-бот остановлен пользователем")
    except Exception as e:
        logger.error(f"❌ Ошибка при запуске Telegram-бота: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main() 