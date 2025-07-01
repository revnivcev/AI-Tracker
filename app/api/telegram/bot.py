import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
from app.config import settings
from app.services.tracker_service import TrackerService
from app.services.llm_service import LLMService
from app.services.whisper_service import WhisperService
from app.services.command_analyzer import CommandAnalyzer
from app.core.digest_service import DigestService
from app.models.database import get_db
from app.models.user import User
from app.models.queue import Queue
from typing import Dict, Any

logger = logging.getLogger(__name__)

logger.info("=== TELEGRAM BOT MODULE LOADED ===")


class TelegramBot:
    def __init__(self):
        logger.info("=== TELEGRAM BOT INIT STARTED ===")
        self.scheduler = None
        if settings.DEMO_MODE:
            logger.info("🤖 Запуск в ДЕМО-режиме - Telegram бот не будет работать")
            self.demo_mode = True
            return
            
        if not settings.TELEGRAM_BOT_TOKEN or settings.TELEGRAM_BOT_TOKEN == "your_telegram_bot_token_here":
            logger.error("❌ TELEGRAM_BOT_TOKEN не настроен! Установите DEMO_MODE=true или настройте реальный токен")
            raise ValueError("TELEGRAM_BOT_TOKEN не настроен")
            
        self.application = Application.builder().token(settings.TELEGRAM_BOT_TOKEN).build()
        logger.info("=== APPLICATION BUILT ===")
        
        # Инициализируем сервисы
        self.tracker_service = TrackerService(
            token=settings.YANDEX_TRACKER_TOKEN,
            org_id=settings.YANDEX_ORG_ID,
            cloud_org_id=settings.YANDEX_CLOUD_ORG_ID
        )
        self.llm_service = LLMService()
        self.whisper_service = WhisperService(settings.WHISPER_BASE_URL)
        self.command_analyzer = CommandAnalyzer(self.llm_service)
        self.digest_service = DigestService(self.tracker_service, self.llm_service)
        self.demo_mode = False
        
        # Регистрируем обработчики
        self._register_handlers()
        logger.info("=== TELEGRAM BOT INIT COMPLETED ===")

    def _register_handlers(self):
        """Регистрируем обработчики команд"""
        logger.info("=== REGISTERING HANDLERS ===")
        
        self.application.add_handler(CommandHandler("start", self.start_command))
        logger.info("Registered: start_command")
        
        self.application.add_handler(CommandHandler("add_queue", self.add_queue_command))
        logger.info("Registered: add_queue_command")
        
        self.application.add_handler(CommandHandler("remove_queue", self.remove_queue_command))
        logger.info("Registered: remove_queue_command")
        
        self.application.add_handler(CommandHandler("list_queues", self.list_queues_command))
        logger.info("Registered: list_queues_command")
        
        self.application.add_handler(CommandHandler("show_available_queues", self.show_available_queues_command))
        logger.info("Registered: show_available_queues_command")
        
        self.application.add_handler(CommandHandler("set_schedule", self.set_schedule_command))
        logger.info("Registered: set_schedule_command")
        
        self.application.add_handler(CommandHandler("send_now", self.send_now_command))
        logger.info("Registered: send_now_command")
        
        self.application.add_handler(CommandHandler("create_task", self.create_task_command))
        logger.info("Registered: create_task_command")
        
        self.application.add_handler(CommandHandler("create", self.create_issue_command))
        logger.info("Registered: create_issue_command")
        
        self.application.add_handler(CommandHandler("help", self.help_command))
        logger.info("Registered: help_command")
        
        # Обработчик callback'ов для выбора очереди (ДОЛЖЕН БЫТЬ ПЕРЕД MessageHandler!)
        self.application.add_handler(CallbackQueryHandler(self.handle_callback))
        logger.info("Registered: CallbackQueryHandler")
        
        # Обработчик для текстовых сообщений
        self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_text))
        logger.info("Registered: MessageHandler")
        
        # Обработчик для голосовых сообщений
        self.application.add_handler(MessageHandler(filters.VOICE, self.handle_voice))
        logger.info("Registered: VoiceHandler")
        
        logger.info("=== ALL HANDLERS REGISTERED ===")

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /start"""
        chat_id = str(update.effective_chat.id)
        
        try:
            db = next(get_db())
            
            # Проверяем, существует ли пользователь
            user = db.query(User).filter(User.chat_id == chat_id).first()
            
            if not user:
                # Создаем нового пользователя
                user = User(
                    chat_id=chat_id,
                    tracker_token=settings.YANDEX_TRACKER_TOKEN,
                    org_id=settings.YANDEX_ORG_ID
                )
                db.add(user)
                db.commit()
                
                await update.message.reply_text(
                    "🎉 Добро пожаловать в AI-Tracker!\n\n"
                    "Я помогу вам отслеживать изменения в задачах Яндекс Трекера и создавать дайджесты.\n\n"
                    "Основные команды:\n"
                    "/show_available_queues - показать все доступные очереди\n"
                    "/add_queue <ключ> - добавить очередь для отслеживания\n"
                    "/list_queues - показать ваши очереди\n"
                    "/send_now - получить дайджест сейчас\n"
                    "/create_task <описание> - создать задачу через ИИ анализ (НОВАЯ ФИЧА!)\n"
                    "/create - создать новую задачу\n"
                    "/help - показать справку\n\n"
                    "Используйте /help для получения подробной информации."
                )
            else:
                await update.message.reply_text(
                    "👋 С возвращением! Используйте /help для получения списка команд."
                )
                
        except Exception as e:
            logger.error(f"Ошибка в start_command: {e}")
            await update.message.reply_text("❌ Произошла ошибка при регистрации.")

    async def add_queue_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /add_queue"""
        chat_id = str(update.effective_chat.id)
        
        if not context.args:
            await update.message.reply_text(
                "❌ Укажите ключ очереди.\n"
                "Пример: /add_queue TEST"
            )
            return
        
        queue_key = context.args[0].upper()
        
        try:
            db = next(get_db())
            user = db.query(User).filter(User.chat_id == chat_id).first()
            
            if not user:
                await update.message.reply_text("❌ Сначала зарегистрируйтесь с помощью /start")
                return
            
            # Проверяем, существует ли очередь
            queues = self.tracker_service.get_queues()
            queue_exists = any(q['key'] == queue_key for q in queues)
            
            if not queue_exists:
                await update.message.reply_text(f"❌ Очередь {queue_key} не найдена в вашей организации.")
                return
            
            # Проверяем, не добавлена ли уже очередь
            existing_queue = db.query(Queue).filter(
                Queue.user_id == user.id,
                Queue.queue_key == queue_key
            ).first()
            
            if existing_queue:
                await update.message.reply_text(f"❌ Очередь {queue_key} уже добавлена.")
                return
            
            # Добавляем очередь
            queue = Queue(
                user_id=user.id,
                queue_key=queue_key,
                queue_name=next((q['name'] for q in queues if q['key'] == queue_key), queue_key)
            )
            db.add(queue)
            db.commit()
            
            await update.message.reply_text(f"✅ Очередь {queue_key} успешно добавлена!")
            
        except Exception as e:
            logger.error(f"Ошибка в add_queue_command: {e}")
            await update.message.reply_text("❌ Произошла ошибка при добавлении очереди.")

    async def list_queues_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /list_queues"""
        chat_id = str(update.effective_chat.id)
        
        try:
            db = next(get_db())
            user = db.query(User).filter(User.chat_id == chat_id).first()
            
            if not user:
                await update.message.reply_text("❌ Сначала зарегистрируйтесь с помощью /start")
                return
            
            queues = db.query(Queue).filter(Queue.user_id == user.id).all()
            
            if not queues:
                await update.message.reply_text(
                    "📋 У вас пока нет добавленных очередей.\n"
                    "Используйте /add_queue <ключ> для добавления очереди."
                )
                return
            
            message = "📋 Ваши очереди:\n\n"
            for queue in queues:
                message += f"• {queue.queue_key} - {queue.queue_name}\n"
            
            await update.message.reply_text(message)
            
        except Exception as e:
            logger.error(f"Ошибка в list_queues_command: {e}")
            await update.message.reply_text("❌ Произошла ошибка при получении списка очередей.")

    async def send_now_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /send_now"""
        chat_id = str(update.effective_chat.id)
        
        try:
            # Проверяем, зарегистрирован ли пользователь
            db = next(get_db())
            user = db.query(User).filter(User.chat_id == chat_id).first()
            
            if not user:
                await update.message.reply_text("❌ Сначала зарегистрируйтесь с помощью /start")
                return
            
            # Получаем очереди пользователя
            user_queues = db.query(Queue).filter(Queue.user_id == user.id).all()
            if not user_queues:
                await update.message.reply_text(
                    "❌ У вас нет добавленных очередей.\n"
                    "Сначала добавьте очереди с помощью /add_queue <ключ>"
                )
                return
            
            # Отправляем сообщение о начале обработки
            processing_msg = await update.message.reply_text("📊 Подготавливаю дайджест...")
            
            # Функция для обновления статуса
            async def update_status(status: str):
                await processing_msg.edit_text(status)
            
            # Генерируем дайджесты для всех очередей
            all_digests = []
            for queue in user_queues:
                try:
                    digest = await self.digest_service.generate_digest(
                        user.id, 
                        queue.queue_key, 
                        since_hours=24,
                        status_callback=update_status
                    )
                    if digest:
                        all_digests.append(digest)
                except Exception as e:
                    logger.error(f"Ошибка при генерации дайджеста для очереди {queue.queue_key}: {e}")
                    all_digests.append(f"❌ Ошибка при генерации дайджеста для очереди {queue.queue_key}")
            
            # Отправляем все дайджесты
            if all_digests:
                for digest in all_digests:
                    await update.message.reply_text(digest, parse_mode='HTML')
                await processing_msg.delete()  # Удаляем сообщение о статусе
            else:
                await processing_msg.edit_text("❌ Не удалось сгенерировать дайджесты.")
                
        except Exception as e:
            logger.error(f"Ошибка в send_now_command: {e}")
            await update.message.reply_text("❌ Произошла ошибка при отправке дайджеста.")

    async def create_issue_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /create"""
        chat_id = str(update.effective_chat.id)
        logger.info(f"create_issue_command: chat_id={chat_id}")
        
        try:
            db = next(get_db())
            user = db.query(User).filter(User.chat_id == chat_id).first()
            
            if not user:
                await update.message.reply_text("❌ Сначала зарегистрируйтесь с помощью /start")
                return
            
            queues = db.query(Queue).filter(Queue.user_id == user.id).all()
            logger.info(f"create_issue_command: found {len(queues)} queues for user {user.id}")
            
            if not queues:
                await update.message.reply_text(
                    "❌ У вас нет добавленных очередей.\n"
                    "Сначала добавьте очередь с помощью /add_queue <ключ>"
                )
                return
            
            # Сохраняем состояние для создания задачи
            context.user_data['creating_issue'] = True
            context.user_data['available_queues'] = [q.queue_key for q in queues]
            logger.info(f"create_issue_command: set creating_issue=True, available_queues={context.user_data['available_queues']}")
            
            # Показываем доступные очереди
            keyboard = []
            for queue in queues:
                keyboard.append([InlineKeyboardButton(queue.queue_key, callback_data=f"create_in_{queue.queue_key}")])
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            logger.info(f"create_issue_command: created keyboard with {len(keyboard)} buttons")
            
            await update.message.reply_text(
                "📝 Создание новой задачи\n\n"
                "Выберите очередь для создания задачи:",
                reply_markup=reply_markup
            )
            
        except Exception as e:
            logger.error(f"Ошибка в create_issue_command: {e}")
            await update.message.reply_text("❌ Произошла ошибка при создании задачи.")

    async def handle_voice(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик голосовых сообщений"""
        chat_id = str(update.effective_chat.id)
        
        try:
            # Проверяем, зарегистрирован ли пользователь
            db = next(get_db())
            user = db.query(User).filter(User.chat_id == chat_id).first()
            
            if not user:
                await update.message.reply_text("❌ Сначала зарегистрируйтесь с помощью /start")
                return
            
            # Отправляем сообщение о начале обработки
            processing_msg = await update.message.reply_text("🎤 Получаю голосовое сообщение...")
            
            try:
                # Получаем файл голосового сообщения
                await self.send_processing_status(update, "fetching", processing_msg)
                voice_file = await context.bot.get_file(update.message.voice.file_id)
                audio_data = await voice_file.download_as_bytearray()
                
                # Транскрибируем аудио
                await self.send_processing_status(update, "transcribing", processing_msg)
                transcription = await self.whisper_service.transcribe_audio(audio_data)
                
                if not transcription:
                    await processing_msg.edit_text("❌ Не удалось распознать голосовое сообщение. Попробуйте еще раз.")
                    return
                
                # Показываем транскрипцию
                await processing_msg.edit_text(f"🎤 Распознано: {transcription}\n\n🤖 Анализирую команду...")
                
                # Анализируем транскрипцию как обычный текст
                await self._process_text_message(update, context, transcription, processing_msg)
                
            except Exception as e:
                logger.error(f"Ошибка при обработке голосового сообщения: {e}")
                await processing_msg.edit_text("❌ Произошла ошибка при обработке голосового сообщения.")
                
        except Exception as e:
            logger.error(f"Ошибка в handle_voice: {e}")
            await update.message.reply_text("❌ Произошла ошибка при обработке голосового сообщения.")

    async def handle_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик текстовых сообщений"""
        try:
            text = update.message.text
            chat_id = str(update.effective_chat.id)
            
            logger.info(f"Получено текстовое сообщение от {chat_id}: {text[:50]}...")
            
            # Анализируем текст с помощью CommandAnalyzer
            analysis = await self.command_analyzer.analyze_text(text, int(chat_id))
            command = analysis.get("command", "unknown")
            confidence = analysis.get("confidence", 0.0)
            needs_clarification = analysis.get("needs_clarification", True)
            feature_status = analysis.get("feature_status", "unknown")
            
            logger.info(f"Анализ команды: {command}, уверенность: {confidence}, статус: {feature_status}, нужны уточнения: {needs_clarification}")
            
            # Сохраняем данные анализа в контексте для использования в других методах
            context.user_data['last_analysis_data'] = analysis
            
            # Обновляем контекст разговора
            self.command_analyzer.update_context(chat_id, command, analysis.get("data", {}))
            
            # Если нужны уточнения, запрашиваем их
            if needs_clarification:
                clarification_questions = analysis.get("clarification_questions", [])
                if clarification_questions:
                    response = "\n".join(clarification_questions)
                    await update.message.reply_text(response)
                else:
                    await update.message.reply_text("❓ Не понял команду. Попробуйте использовать /help для списка команд.")
                return
            
            # Выполняем команду
            if command == "send_digest":
                await self.send_now_command(update, context)
            elif command == "create_task":
                await self.create_task_from_text(update, context, text)
            elif command == "set_schedule":
                await self.set_schedule_from_text(update, context, text)
            elif command == "show_queues":
                await self.show_available_queues_command(update, context)
            else:
                await update.message.reply_text("❓ Не понял команду. Попробуйте использовать /help для списка команд.")
                
        except Exception as e:
            logger.error(f"Ошибка в handle_text_message: {e}")
            await update.message.reply_text("❌ Произошла ошибка при обработке сообщения.")

    async def create_task_from_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE, text: str):
        """Создать задачу из текстового описания"""
        try:
            chat_id = str(update.effective_chat.id)
            
            # Отправляем статус
            status_msg = await update.message.reply_text("🤖 Анализирую описание задачи...")
            
            # Получаем данные из анализа намерений (если есть)
            analysis_data = context.user_data.get('last_analysis_data', {})
            extracted_data = analysis_data.get('data', {})
            
            # Если у нас есть готовые данные из анализа намерений, используем их
            if extracted_data and extracted_data.get('summary') and extracted_data.get('description'):
                logger.info(f"Используем данные из анализа намерений: {extracted_data}")
                
                # Используем отрефакторенные данные, если они есть
                summary = extracted_data.get('refactored_text') or extracted_data.get('summary')
                description = extracted_data.get('description')
                
                # Показываем информацию о рефакторинге
                refactoring_changes = extracted_data.get('refactoring_changes', [])
                if refactoring_changes:
                    refactoring_info = f"💡 Улучшения: {', '.join(refactoring_changes[:2])}"
                    await status_msg.edit_text(f"📝 {refactoring_info}\n\n🤖 Создаю задачу...")
                else:
                    await status_msg.edit_text("📋 Создаю задачу...")
                
                parsed = {
                    'summary': summary,
                    'description': description,
                    'queue': extracted_data.get('queue'),
                    'priority': extracted_data.get('priority'),
                    'assignee': extracted_data.get('assignee'),
                    'type': extracted_data.get('type'),
                    'tags': extracted_data.get('tags')
                }
            else:
                # Парсим описание с помощью LLM
                parsed = await self.llm_service.parse_issue_description(text)
                await status_msg.edit_text("📋 Создаю задачу...")
            
            # Получаем очереди пользователя
            db = next(get_db())
            user = db.query(User).filter(User.chat_id == chat_id).first()
            if not user:
                await status_msg.edit_text("❌ Сначала зарегистрируйтесь с помощью /start")
                return
            
            user_queues = db.query(Queue).filter(Queue.user_id == user.id).all()
            if not user_queues:
                await status_msg.edit_text("❌ У вас нет добавленных очередей. Добавьте очередь с помощью /add_queue")
                return
            
            # Используем очередь из анализа или первую доступную
            queue_key = parsed.get('queue') or user_queues[0].queue_key
            
            # Создаем задачу
            issue = self.tracker_service.create_issue(
                queue_key=queue_key,
                summary=parsed['summary'],
                description=parsed['description'],
                assignee=parsed.get('assignee'),
                priority=parsed.get('priority', 'Medium')
            )
            
            if issue:
                issue_url = f"https://tracker.yandex.ru/{issue['key']}"
                
                # Формируем сообщение с информацией о рефакторинге
                message = f"✅ Задача создана!\n\n"
                message += f"📋 [{issue['key']}]({issue_url})\n"
                message += f"📝 {issue['summary']}\n"
                message += f"👤 Исполнитель: {issue.get('assignee', 'Не назначен')}\n"
                message += f"⚡ Приоритет: {issue.get('priority', 'Средний')}"
                
                # Добавляем информацию о рефакторинге, если есть
                if extracted_data.get('refactoring_changes'):
                    message += f"\n\n💡 Улучшения: {', '.join(extracted_data['refactoring_changes'][:3])}"
                
                await status_msg.edit_text(message, parse_mode='HTML')
            else:
                await status_msg.edit_text("❌ Не удалось создать задачу. Попробуйте позже.")
                
        except Exception as e:
            logger.error(f"Ошибка при создании задачи из текста: {e}")
            await update.message.reply_text("❌ Произошла ошибка при создании задачи.")

    async def set_schedule_from_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE, text: str):
        """Установить расписание из текста"""
        try:
            chat_id = str(update.effective_chat.id)
            
            # Извлекаем время из текста
            import re
            time_match = re.search(r'(\d{1,2}):(\d{2})', text)
            if not time_match:
                await update.message.reply_text("❌ Укажите время в формате HH:MM. Пример: 09:30")
                return
            
            hour, minute = map(int, time_match.groups())
            if not (0 <= hour < 24 and 0 <= minute < 60):
                await update.message.reply_text("❌ Некорректный формат времени. Пример: 09:30")
                return
            
            schedule_time = f"{hour:02d}:{minute:02d}"
            
            # Обновляем расписание
            if hasattr(self, 'scheduler') and self.scheduler:
                success = self.scheduler.update_user_schedule(chat_id, schedule_time)
                if success:
                    await update.message.reply_text(f"⏰ Время дайджеста изменено на {schedule_time}. Дайджесты будут приходить ежедневно в это время.")
                else:
                    await update.message.reply_text("❌ Не удалось изменить расписание. Попробуйте позже.")
            else:
                await update.message.reply_text("❌ Планировщик недоступен.")
                
        except Exception as e:
            logger.error(f"Ошибка при установке расписания из текста: {e}")
            await update.message.reply_text("❌ Произошла ошибка при изменении расписания.")

    async def handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик callback'ов"""
        logger.info("=== CALLBACK HANDLER CALLED ===")
        logger.info(f"=== UPDATE TYPE: {type(update)} ===")
        logger.info(f"=== UPDATE: {update} ===")
        
        try:
            query = update.callback_query
            chat_id = str(query.message.chat.id) if query.message else 'unknown'
            logger.info(f"handle_callback: chat_id={chat_id}, data={query.data}, user_data={context.user_data}")
            await query.answer()
            
            if query.data.startswith("create_in_"):
                queue_key = query.data.replace("create_in_", "")
                context.user_data['selected_queue'] = queue_key
                context.user_data['creating_issue'] = True
                logger.info(f"handle_callback: set selected_queue={queue_key}, creating_issue=True for chat_id={chat_id}")
                
                await query.edit_message_text(
                    f"📝 Создание задачи в очереди {queue_key}\n\n"
                    "Опишите задачу в следующем сообщении.\n"
                    "Например: 'Нужно исправить баг в авторизации'"
                )
                logger.info(f"handle_callback: sent message asking for task description")
            else:
                logger.info(f"handle_callback: unknown callback data: {query.data}")
                
        except Exception as e:
            logger.error(f"handle_callback: ERROR: {e}")
            logger.error(f"handle_callback: update={update}")
            logger.error(f"handle_callback: context={context}")

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /help"""
        help_text = """
🤖 <b>AI-Tracker</b> - Умный помощник по работе с Yandex Tracker

📊 <b>Core-функции (стабильные):</b>
• <code>/send_now</code> - Получить дайджест сейчас
• <code>/show_available_queues</code> - Показать доступные очереди
• <code>/add_queue &lt;ключ&gt;</code> - Добавить очередь для отслеживания
• <code>/list_queues</code> - Показать ваши очереди
• <code>/set_schedule HH:MM</code> - Установить время дайджеста

🤖 <b>Beta-функции (в разработке):</b>
• <code>/create_task</code> - Создать задачу через ИИ анализ
• Свободный текст: "создай задачу исправить баг"
• Свободный текст: "установи расписание на 10:00"

🎤 <b>Alpha-функции (экспериментальные):</b>
• Голосовые сообщения - транскрибация и анализ
• Произвольные запросы к боту на естественном языке

📝 <b>Примеры использования:</b>

<b>Core-функции:</b>
<code>
/send_now
/show_available_queues
/add_queue TEST
/set_schedule 09:00
</code>

<b>Beta-функции (свободный текст):</b>
<code>
покажи дайджест
создай задачу исправить баг в авторизации
установи расписание на 19:30
покажи очереди
</code>

<b>Alpha-функции:</b>
<code>
🎤 Отправьте голосовое сообщение
</code>

🔧 <b>Поддержка:</b>
• Разработчик: @mokyzzzee
• Проблемы и предложения: создавайте issues в репозитории

💡 <b>Советы:</b>
• Core-функции работают стабильно
• Beta-функции могут требовать уточнений
• Alpha-функции в экспериментальном режиме
"""
        await update.message.reply_text(help_text, parse_mode='HTML')

    async def set_schedule_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /set_schedule <HH:MM>"""
        chat_id = str(update.effective_chat.id)
        if not context.args or len(context.args[0]) != 5 or ':' not in context.args[0]:
            await update.message.reply_text("❌ Укажите время в формате HH:MM. Пример: /set_schedule 09:30")
            return
        schedule_time = context.args[0]
        try:
            hour, minute = map(int, schedule_time.split(':'))
            if not (0 <= hour < 24 and 0 <= minute < 60):
                raise ValueError
        except Exception:
            await update.message.reply_text("❌ Некорректный формат времени. Пример: /set_schedule 09:30")
            return
        try:
            db = next(get_db())
            user = db.query(User).filter(User.chat_id == chat_id).first()
            if not user:
                await update.message.reply_text("❌ Сначала зарегистрируйтесь с помощью /start")
                return
            user.digest_schedule = schedule_time
            db.commit()
            # Вызовем планировщик для обновления расписания
            if hasattr(self, 'scheduler') and self.scheduler:
                self.scheduler.update_user_schedule(user.chat_id, schedule_time)
            await update.message.reply_text(f"⏰ Время дайджеста изменено на {schedule_time}. Дайджесты будут приходить ежедневно в это время.")
        except Exception as e:
            logger.error(f"Ошибка в set_schedule_command: {e}")
            await update.message.reply_text("❌ Не удалось изменить расписание. Попробуйте позже.")

    async def remove_queue_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /remove_queue"""
        # Заглушка для будущей реализации
        await update.message.reply_text("🗑️ Функция удаления очереди будет доступна в следующей версии.")

    async def show_available_queues_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /show_available_queues"""
        chat_id = str(update.effective_chat.id)
        
        try:
            db = next(get_db())
            user = db.query(User).filter(User.chat_id == chat_id).first()
            
            if not user:
                await update.message.reply_text("❌ Сначала зарегистрируйтесь с помощью /start")
                return
            
            queues = self.tracker_service.get_queues()
            
            if not queues:
                await update.message.reply_text("❌ У вас нет доступных очередей в Yandex Tracker.")
                return
            
            message = "📋 Доступные очереди:\n\n"
            for queue in queues:
                message += f"• {queue['key']} - {queue['name']}\n"
            
            await update.message.reply_text(message)
            
        except Exception as e:
            logger.error(f"Ошибка в show_available_queues_command: {e}")
            await update.message.reply_text("❌ Произошла ошибка при получении списка доступных очередей.")

    async def create_task_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /create_task - создание задачи через LLM анализ"""
        chat_id = str(update.effective_chat.id)
        
        try:
            db = next(get_db())
            user = db.query(User).filter(User.chat_id == chat_id).first()
            
            if not user:
                await update.message.reply_text("❌ Сначала зарегистрируйтесь с помощью /start")
                return
            
            # Получаем очереди пользователя
            user_queues = db.query(Queue).filter(Queue.user_id == user.id).all()
            if not user_queues:
                await update.message.reply_text(
                    "❌ У вас нет добавленных очередей.\n"
                    "Сначала добавьте очереди с помощью /add_queue <ключ>"
                )
                return
            
            # Проверяем, есть ли текст после команды
            if not context.args:
                await update.message.reply_text(
                    "📝 Опишите задачу, которую нужно создать.\n\n"
                    "Примеры:\n"
                    "• /create_task Нужно исправить баг в авторизации\n"
                    "• /create_task Создать документацию для API\n"
                    "• /create_task Добавить новую функцию поиска с высоким приоритетом\n\n"
                    "Я проанализирую ваш текст и создам задачу с подходящими параметрами!"
                )
                return
            
            # Объединяем все аргументы в один текст
            task_description = " ".join(context.args)
            
            # Отправляем сообщение о начале обработки
            processing_msg = await update.message.reply_text("🤖 Анализирую ваш запрос...")
            
            try:
                # Получаем доступные очереди
                available_queues = [q.queue_key for q in user_queues]
                
                # Получаем доступные приоритеты из Yandex Tracker
                priorities = self.tracker_service.get_priorities()
                available_priorities = [p['display'] for p in priorities] if priorities else ["Низкий", "Средний", "Высокий", "Критический"]
                
                # Анализируем текст через LLM
                task_data = await self.llm_service.analyze_and_create_task(task_description, available_queues, available_priorities)
                
                if not task_data.get('queue'):
                    await processing_msg.edit_text("❌ Не удалось определить очередь для задачи.")
                    return
                
                # Обновляем сообщение с результатом анализа
                analysis_text = f"""
📋 Результат анализа:

📝 Название: {task_data['summary']}
📄 Описание: {task_data['description'][:200]}{'...' if len(task_data['description']) > 200 else ''}
🏷️ Приоритет: {task_data['priority']}
👤 Исполнитель: {task_data['assignee'] or 'Не назначен'}
📂 Очередь: {task_data['queue']}
📅 Срок: {task_data['deadline'] or 'Не установлен'}
🏷️ Теги: {task_data['tags'] or 'Нет'}

Создаю задачу...
                """
                await processing_msg.edit_text(analysis_text)
                
                # Создаем задачу в Yandex Tracker
                created_issue = self.tracker_service.create_issue(
                    queue_key=task_data['queue'],
                    summary=task_data['summary'],
                    description=task_data['description'],
                    assignee=task_data['assignee'],
                    priority=task_data['priority']
                )
                
                if created_issue:
                    success_text = f"""
✅ Задача успешно создана!

🔗 {created_issue['key']}: {created_issue['summary']}
📂 Очередь: {created_issue['queue']}
📊 Статус: {created_issue['status']}
🌐 Ссылка: {created_issue['url']}

Задача готова к работе! 🚀
                    """
                    await processing_msg.edit_text(success_text)
                else:
                    await processing_msg.edit_text("❌ Ошибка при создании задачи в Yandex Tracker.")
                    
            except Exception as e:
                logger.error(f"Ошибка при создании задачи: {e}")
                await processing_msg.edit_text(f"❌ Произошла ошибка при создании задачи: {str(e)}")
                
        except Exception as e:
            logger.error(f"Ошибка в create_task_command: {e}")
            await update.message.reply_text("❌ Произошла ошибка при обработке команды.")

    def run_polling(self):
        logger.info("Запуск Telegram бота...")
        self.application.run_polling(allowed_updates=["message", "callback_query"])

    async def send_status(self, update: Update, message: str, edit_message=None):
        """Отправить статус работы"""
        try:
            if edit_message:
                await edit_message.edit_text(message)
            else:
                await update.message.reply_text(message)
        except Exception as e:
            logger.error(f"Ошибка при отправке статуса: {e}")

    async def send_processing_status(self, update: Update, status: str, edit_message=None):
        """Отправить статус обработки с эмодзи"""
        status_emoji = {
            "analyzing": "🤖 Анализирую...",
            "creating": "🔄 Создаю...",
            "transcribing": "🎤 Транскрибирую...",
            "fetching": "📡 Получаю данные...",
            "processing": "⚙️ Обрабатываю...",
            "sending": "📤 Отправляю..."
        }
        
        emoji_text = status_emoji.get(status, "⏳ Обрабатываю...")
        await self.send_status(update, emoji_text, edit_message) 