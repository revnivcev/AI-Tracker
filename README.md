# 🤖 AI-Tracker - AI-Агент для Yandex Tracker

[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Docker](https://img.shields.io/badge/Docker-Ready-blue.svg)](https://www.docker.com/)
[![Telegram](https://img.shields.io/badge/Telegram-Bot-blue.svg)](https://core.telegram.org/bots/)
[![Yandex Tracker](https://img.shields.io/badge/Yandex%20Tracker-API-orange.svg)](https://tracker.yandex.ru/)

> **AI-Tracker** - это интеллектуальный Telegram бот, который автоматизирует работу с Yandex Tracker через естественный язык и локальный ИИ (Ollama).

## 🚀 Возможности

### 📊 Core-функции (стабильные)
- **Автоматические дайджесты** - ежедневные отчеты о задачах
- **Управление очередями** - добавление/удаление очередей для отслеживания
- **Гибкое расписание** - настройка времени отправки дайджестов
- **Мгновенные отчеты** - получение дайджеста по запросу
- **Поддержка Cloud-организации Yandex Tracker** – обращайте на это внимание при работе с приложением

### 🤖 Beta-функции (в разработке)
- **Умное создание задач** - ИИ анализирует текст и создает задачи
- **Естественный язык** - команды на русском языке
- **Автоматический парсинг** - извлечение параметров задачи из текста
- **Рефакторинг описаний** - улучшение текста задач ИИ
- **Поддержка GigaChat API** – для работы со сложными проектами

### 🎤 Alpha-функции (экспериментальные)
- **Голосовые сообщения** - распознавание речи через Whisper
- **Произвольные запросы** - анализ любых сообщений ИИ
- **Контекстное понимание** - запоминание предыдущих команд

## 🏗️ Архитектура

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Telegram Bot  │◄──►│   AI-Tracker    │◄──►│  Yandex Tracker │
│                 │    │   Application   │    │      API        │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                              │
                              ▼
                       ┌─────────────────┐
                       │   PostgreSQL    │
                       │   Database      │
                       └─────────────────┘
                              │
                              ▼
                       ┌─────────────────┐    ┌─────────────────┐
                       │   Ollama LLM    │    │   Whisper ASR   │
                       │   (Local AI)    │    │  (Speech-to-Text)│
                       └─────────────────┘    └─────────────────┘
```

## 📋 Требования

- **Docker** и **Docker Compose**
- **Python 3.10+** (для локальной разработки)
- **Telegram Bot Token** (от @BotFather)
- **Yandex Tracker Token** и **Organization ID**
- **4GB+ RAM** (для работы с локальным ИИ)

## 🚀 Быстрый старт

### 1. Клонирование репозитория
```bash
git clone https://github.com/your-username/ai-tracker.git
cd ai-tracker
```

### 2. Настройка переменных окружения
```bash
cp env.example .env
```

Отредактируйте `.env` файл:
```env
# Telegram Bot
TELEGRAM_BOT_TOKEN=your_telegram_bot_token_here

# Yandex Tracker
YANDEX_TRACKER_TOKEN=your_yandex_tracker_token_here
YANDEX_CLOUD_ORG_ID=your_cloud_organization_id_here

# LLM Configuration
LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://ollama:11434
OLLAMA_MODEL=Vikhr-Gemma-2B-instruct-GGUF

# Application settings
LOG_LEVEL=INFO
DIGEST_SCHEDULE=09:00
```

### 3. Запуск через Docker
```bash
# Сборка и запуск всех сервисов
docker compose up -d

# Проверка статуса
docker compose ps

# Просмотр логов
docker compose logs -f app
```

### 4. Первоначальная настройка

1. **Отправьте `/start`** боту в Telegram
2. **Добавьте очереди**: `/add_queue <ключ_очереди>`
3. **Настройте расписание**: `/set_schedule 09:00`
4. **Получите дайджест**: `/send_now`

## 📖 Подробная документация

### 🔧 Настройка API ключей

#### Telegram Bot Token
1. Найдите @BotFather в Telegram
2. Отправьте `/newbot`
3. Следуйте инструкциям
4. Скопируйте полученный токен в `.env`

#### Yandex Tracker Token
1. Откройте [Yandex Tracker](https://tracker.yandex.ru/)
2. Перейдите в **Настройки** → **Интеграции** → **API**
3. Создайте приложение
4. Получите OAUTH токен
5. Скопируйте **токен** и **Organization ID** в `.env`

### 🐳 Docker команды

```bash
# Запуск всех сервисов
docker compose up -d

# Остановка всех сервисов
docker compose down

# Пересборка с изменениями
docker compose build --no-cache
docker compose up -d

# Просмотр логов конкретного сервиса
docker compose logs -f app
docker compose logs -f ollama
docker compose logs -f postgres

# Вход в контейнер приложения
docker compose exec app bash

# Проверка переменных окружения
docker compose exec app env | grep YANDEX
```

### 🤖 Команды бота

#### Core-команды
```bash
/start                    # Запуск бота
/help                     # Справка
/send_now                 # Получить дайджест сейчас
/show_available_queues    # Показать доступные очереди
/add_queue <ключ>         # Добавить очередь для отслеживания
/remove_queue <ключ>      # Удалить очередь
/list_queues              # Показать ваши очереди
/set_schedule HH:MM       # Установить время дайджеста
```

#### Beta-команды (естественный язык)
```bash
"покажи дайджест"                    # Получить дайджест
"создай задачу исправить баг"        # Создать задачу
"установи расписание на 19:30"       # Настроить расписание
"покажи очереди"                     # Список очередей
```

#### Alpha-команды
```bash
🎤 Голосовое сообщение              # Распознавание речи
```

### 🔍 Устранение неполадок

#### Бот не отвечает
```bash
# Проверьте статус контейнеров
docker compose ps

# Проверьте логи
docker compose logs app

# Проверьте переменные окружения
docker compose exec app env | grep TELEGRAM
```

#### Ошибки Yandex Tracker API
```bash
# Проверьте токен и Organization ID
docker compose exec app env | grep YANDEX

# Проверьте логи API запросов
docker compose logs app | grep "Yandex Tracker"
```

#### Проблемы с LLM
```bash
# Проверьте статус Ollama
docker compose logs ollama

# Проверьте загруженные модели
docker compose exec ollama ollama list
```

## 🛠️ Разработка

### Локальная разработка
```bash
# Установка зависимостей
pip install -r requirements.txt

# Настройка базы данных
# (используйте Docker для PostgreSQL)

# Запуск приложения
python -m app.main
```

### Структура проекта
```
ai-tracker/
├── app/
│   ├── core/           # Основная логика
│   ├── models/         # Модели базы данных
│   ├── services/       # Сервисы (Tracker, LLM, Whisper)
│   ├── telegram/       # Telegram бот
│   └── scheduler/      # Планировщик дайджестов
├── docker-compose.yml  # Конфигурация Docker
├── Dockerfile         # Образ приложения
├── requirements.txt   # Python зависимости
└── README.md         # Документация
```

### Добавление новых функций
1. Создайте новый сервис в `app/services/`
2. Добавьте обработчик в `app/telegram/bot.py`
3. Обновите документацию
4. Протестируйте через Docker

## 📊 Мониторинг

### Логи
```bash
# Все логи
docker compose logs

# Логи приложения
docker compose logs app

# Логи в реальном времени
docker compose logs -f app
```

### Метрики
- Количество обработанных сообщений
- Время ответа API
- Статистика использования команд
- Ошибки и исключения

## 🤝 Вклад в проект

1. Форкните репозиторий
2. Создайте ветку для новой функции
3. Внесите изменения
4. Добавьте тесты
5. Создайте Pull Request

## 📄 Лицензия

MIT License - см. файл [LICENSE](LICENSE)

## 🆘 Поддержка

- **Issues**: [GitHub Issues](https://github.com/your-username/ai-tracker/issues)
- **Discussions**: [GitHub Discussions](https://github.com/your-username/ai-tracker/discussions)
- **Email**: revnivcev208@gmail.com
- **TG**: @mokyzzzee

## 🙏 Благодарности

- [Yandex Tracker API](https://tracker.yandex.ru/)
- [Ollama](https://ollama.ai/) - локальный ИИ
- [python-telegram-bot](https://python-telegram-bot.org/)
- [Whisper](https://openai.com/research/whisper) - распознавание речи
- Yandex Tracker Client
- Vikhr

---

**⭐ Если проект вам понравился, поставьте звезду на GitHub!** # AI-Traacker
