import asyncio
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
from app.config import settings
from app.services.tracker_service import TrackerService
from app.services.llm_service import LLMService
from app.services.command_analyzer import CommandAnalyzer
from app.core.digest_service import DigestService
from app.models.database import get_db
from app.models.user import User
from app.models.queue import Queue
from typing import Dict, Any, List

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
        

        

        
        self.application.add_handler(CommandHandler("help", self.help_command))
        logger.info("Registered: help_command")
        
        # Обработчик callback'ов для выбора очереди (ДОЛЖЕН БЫТЬ ПЕРЕД MessageHandler!)
        self.application.add_handler(CallbackQueryHandler(self.handle_callback))
        logger.info("Registered: CallbackQueryHandler")
        
        # Обработчик для текстовых сообщений
        self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_text))
        logger.info("Registered: MessageHandler")
        

        
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
        
        # МГНОВЕННЫЙ ОТВЕТ - пользователь понимает, что бот работает
        processing_msg = await update.message.reply_text(f"🔍 Проверяю очередь {queue_key}...")
        
        try:
            db = next(get_db())
            user = db.query(User).filter(User.chat_id == chat_id).first()
            
            if not user:
                await processing_msg.edit_text("❌ Сначала зарегистрируйтесь с помощью /start")
                return
            
            # Проверяем, существует ли очередь
            await processing_msg.edit_text(f"🔍 Проверяю доступность очереди {queue_key}...")
            queues = self.tracker_service.get_queues()
            queue_exists = any(q['key'] == queue_key for q in queues)
            
            if not queue_exists:
                await processing_msg.edit_text(f"❌ Очередь {queue_key} не найдена в вашей организации.")
                return
            
            # Проверяем, не добавлена ли уже очередь
            await processing_msg.edit_text(f"🔍 Проверяю, не добавлена ли уже очередь {queue_key}...")
            existing_queue = db.query(Queue).filter(
                Queue.user_id == user.id,
                Queue.queue_key == queue_key
            ).first()
            
            if existing_queue:
                await processing_msg.edit_text(f"❌ Очередь {queue_key} уже добавлена.")
                return
            
            # Добавляем очередь
            await processing_msg.edit_text(f"➕ Добавляю очередь {queue_key}...")
            queue = Queue(
                user_id=user.id,
                queue_key=queue_key,
                queue_name=next((q['name'] for q in queues if q['key'] == queue_key), queue_key)
            )
            db.add(queue)
            db.commit()
            
            await processing_msg.edit_text(f"✅ Очередь {queue_key} успешно добавлена!")
            
        except Exception as e:
            logger.error(f"Ошибка в add_queue_command: {e}")
            await processing_msg.edit_text("❌ Произошла ошибка при добавлении очереди.")

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
            
            # МГНОВЕННЫЙ ОТВЕТ - пользователь понимает, что бот работает
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



    async def handle_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик текстовых сообщений"""
        if not update.message:
            logger.error("update.message is None")
            return
            
        chat_id = str(update.effective_chat.id)
        text = update.message.text.strip()
        
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
            
            # МГНОВЕННЫЙ ОТВЕТ - пользователь понимает, что бот работает
            processing_msg = await update.message.reply_text("🤖 Анализирую ваше сообщение...")
            
            # Получаем доступные очереди и приоритеты
            available_queues = [q.queue_key for q in user_queues]
            priorities = self.tracker_service.get_priorities()
            available_priorities = [p['display'] for p in priorities] if priorities else ["Низкий", "Средний", "Высокий", "Критический"]
            
            # Анализируем свободное сообщение пользователя
            analysis = await self.llm_service.analyze_free_conversation(
                user_message=text,
                available_queues=available_queues,
                available_priorities=available_priorities,
                user_context=f"Пользователь: {user.chat_id}, Очереди: {available_queues}"
            )
            
            logger.info(f"Анализ свободного общения: {analysis}")
            
            # Обрабатываем результат анализа
            intent = analysis.get('intent', 'unknown')
            action = analysis.get('action', 'help')
            response = analysis.get('response', 'Не понял, что вы хотите')
            data = analysis.get('data', {})
            
            # Логируем детали для отладки
            logger.info(f"Intent: {intent}, Action: {action}")
            logger.info(f"Task data: {data.get('task_data', {})}")
            logger.info(f"Queue key: {data.get('queue_key')}")
            
            # Обновляем сообщение с результатом
            await processing_msg.edit_text(response)
            
            # Выполняем действие на основе анализа
            if action == 'create_task':
                task_data = data.get('task_data', {})
                queue_key = data.get('queue_key')
                
                # Проверяем, есть ли достаточно данных для создания задачи
                if task_data.get('summary'):
                    # Создаем задачу с реальными данными
                    await self._create_task_from_analysis(update, task_data, queue_key)
                else:
                    # Запрашиваем дополнительную информацию
                    await update.message.reply_text(
                        "📝 Пожалуйста, опишите задачу подробнее:\n"
                        "• Что нужно сделать?\n"
                        "• Какие требования?\n"
                        "• Есть ли сроки?\n"
                        "• Кто исполнитель?"
                    )
            
            elif action == 'show_digest':
                # Показываем дайджест
                await self._show_digest_for_user(update, user, available_queues)
            
            elif action == 'set_schedule':
                schedule_time = data.get('schedule_time')
                if schedule_time:
                    await self._set_schedule_from_analysis(update, user, schedule_time)
                else:
                    await update.message.reply_text(
                        "⏰ Укажите время для дайджеста в формате HH:MM (UTC)\n"
                        "Например: 09:00 (будет 12:00 МСК)"
                    )
            
            elif action == 'help':
                await self.help_command(update, context)
            
            else:
                # Общий ответ для неизвестных намерений
                await update.message.reply_text(
                    "🤖 Я понимаю, что вы хотите что-то сделать. Попробуйте:\n"
                    "• Создать задачу\n"
                    "• Показать дайджест\n"
                    "• Установить расписание\n"
                    "• Показать очереди"
                )
                
        except Exception as e:
            logger.error(f"Ошибка в handle_text: {e}")
            await update.message.reply_text("❌ Произошла ошибка при обработке сообщения. Попробуйте позже.")

    async def _create_task_from_analysis(self, update: Update, task_data: Dict[str, Any], queue_key: str):
        """Создать задачу на основе анализа"""
        try:
            # Подготавливаем данные для создания задачи
            summary = task_data.get('summary', 'Новая задача')
            description = task_data.get('description', summary)
            assignee = task_data.get('assignee')
            priority = task_data.get('priority', 'Средний')
            deadline = task_data.get('deadline')
            
            # Если очередь не указана, используем первую доступную
            if not queue_key:
                db = next(get_db())
                user = db.query(User).filter(User.chat_id == str(update.effective_chat.id)).first()
                if user:
                    user_queues = db.query(Queue).filter(Queue.user_id == user.id).all()
                    if user_queues:
                        queue_key = user_queues[0].queue_key
            
            if not queue_key:
                await update.message.reply_text("❌ Не удалось определить очередь для задачи. Добавьте очередь с помощью /add_queue")
                return
            
            # Создаем задачу в Yandex Tracker
            created_issue = self.tracker_service.create_issue(
                queue_key=queue_key,
                summary=summary,
                description=description,
                assignee=assignee,
                priority=priority
            )
            
            if created_issue:
                success_text = f"""
✅ Задача успешно создана!

🔗 {created_issue['key']}: {created_issue['summary']}
📂 Очередь: {created_issue['queue']}
📊 Статус: {created_issue['status']}
🌐 Ссылка: {created_issue['url']}
"""
                
                if deadline:
                    success_text += f"📅 Дедлайн: {deadline}\n"
                
                success_text += "\nЗадача готова к работе! 🚀"
                
                await update.message.reply_text(success_text)
            else:
                await update.message.reply_text("❌ Ошибка при создании задачи в Yandex Tracker.")
                
        except Exception as e:
            logger.error(f"Ошибка при создании задачи: {e}")
            await update.message.reply_text(f"❌ Произошла ошибка при создании задачи: {str(e)}")

    async def _show_digest_for_user(self, update: Update, user: User, available_queues: List[str]):
        """Показать дайджест для пользователя"""
        try:
            # Показываем дайджест для первой очереди (можно улучшить выбор)
            if available_queues:
                queue_key = available_queues[0]
                
                # Отправляем сообщение о начале обработки
                processing_msg = await update.message.reply_text("📊 Формирую дайджест...")
                
                async def update_status(status: str):
                    await processing_msg.edit_text(f"📊 {status}")
                
                # Генерируем дайджест
                digest = await self.digest_service.generate_digest(
                    user_id=user.id,
                queue_key=queue_key,
                    since_hours=24,
                    status_callback=update_status
                )
                
                if digest:
                    await processing_msg.edit_text(digest, parse_mode='HTML')
                else:
                    await processing_msg.edit_text("❌ Не удалось сформировать дайджест.")
            else:
                await update.message.reply_text("❌ У вас нет доступных очередей для дайджеста.")
                
        except Exception as e:
            logger.error(f"Ошибка при показе дайджеста: {e}")
            await update.message.reply_text("❌ Произошла ошибка при формировании дайджеста.")

    async def _set_schedule_from_analysis(self, update: Update, user: User, schedule_time: str):
        """Установить расписание на основе анализа"""
        try:
            # Обновляем расписание в базе
            user.digest_schedule = schedule_time
            db = next(get_db())
            db.commit()
            
            # Обновляем планировщик
            if hasattr(self, 'scheduler') and self.scheduler:
                self.scheduler.update_user_schedule(user.chat_id, schedule_time)
            
            await update.message.reply_text(
                f"⏰ Время дайджеста изменено на {schedule_time} UTC (Мск -3). "
                "Дайджесты будут приходить ежедневно в это время."
            )
                
        except Exception as e:
            logger.error(f"Ошибка при установке расписания: {e}")
            await update.message.reply_text("❌ Не удалось изменить расписание. Попробуйте позже.")

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
• <code>/set_schedule HH:MM</code> - Установить время дайджеста (время указывается в UTC, Мск -3)

🤖 <b>Beta-функции (в разработке):</b>
• Свободный текст: "создай задачу исправить баг"
• Свободный текст: "установи расписание на 10:00"
• Свободный текст: "покажи дайджест"

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

⏰ <b>Важно:</b> Время указывается в UTC (Москва -3 часа)
• 09:00 UTC = 12:00 МСК
• 18:00 UTC = 21:00 МСК

🔧 <b>Поддержка:</b>
• Разработчик: @mokyzzzee
• Проблемы и предложения: создавайте issues в репозитории

💡 <b>Советы:</b>
• Core-функции работают стабильно
• Beta-функции могут требовать уточнений
• Просто напишите задачу текстом - ИИ сам разберется!
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
            await update.message.reply_text(f"⏰ Время дайджеста изменено на {schedule_time} UTC (Мск -3). Дайджесты будут приходить ежедневно в это время.")
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