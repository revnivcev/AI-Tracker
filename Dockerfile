FROM python:3.11-slim

WORKDIR /app

# Установка системных зависимостей
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Копирование зависимостей
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копирование .env файла
COPY .env .

# Копирование кода приложения
COPY app/ ./app/

# Копирование entrypoint для Telegram-бота
COPY telegram_bot.py .

# Создание директории для логов
RUN mkdir -p logs

# Запуск приложения
CMD ["python", "-m", "app.main"] 