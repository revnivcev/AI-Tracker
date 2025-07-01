import logging
from datetime import datetime, time
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from app.models.database import get_db
from app.models.user import User
from app.models.queue import Queue
from app.services.tracker_service import TrackerService
from app.services.llm_service import LLMService
from app.core.digest_service import DigestService
from app.config import settings
from app.tg_bot.bot import TelegramBot

logger = logging.getLogger(__name__)


class DigestScheduler:
    def __init__(self, telegram_bot: TelegramBot):
        self.telegram_bot = telegram_bot
        self.scheduler = AsyncIOScheduler()
        
        # Создаем TrackerService с правильными параметрами
        self.tracker_service = TrackerService(
            token=settings.YANDEX_TRACKER_TOKEN,
            org_id=settings.YANDEX_ORG_ID,
            cloud_org_id=settings.YANDEX_CLOUD_ORG_ID
        )
        
        self.digest_service = DigestService(
            self.tracker_service,
            LLMService()
        )

    def start(self):
        """Запустить планировщик"""
        logger.info("Запуск планировщика дайджестов...")
        
        # Добавляем задачу для ежедневного дайджеста в 9:00
        self.scheduler.add_job(
            self._send_daily_digest,
            CronTrigger(hour=9, minute=0),
            id="Ежедневный дайджест",
            name="Ежедневный дайджест в 9:00"
        )
        
        # Запускаем планировщик
        self.scheduler.start()
        logger.info("Планировщик дайджестов запущен")
        
        # Загружаем пользовательские расписания
        self._load_user_schedules()

    def _load_user_schedules(self):
        """Загрузить расписания пользователей из базы данных"""
        try:
            logger.info("Загрузка пользовательских расписаний...")
            db = next(get_db())
            users = db.query(User).filter(User.digest_schedule.isnot(None)).all()
            
            logger.info(f"Найдено {len(users)} пользователей с расписанием")
            
            for user in users:
                try:
                    # Парсим время из строки
                    time_parts = user.digest_schedule.split(':')
                    hour = int(time_parts[0])
                    minute = int(time_parts[1])
                    
                    logger.info(f"Добавляю джоб для пользователя {user.chat_id} в {hour}:{minute:02d}")
                    
                    # Добавляем задачу для пользователя
                    job_id = f"user_digest_{user.chat_id}"
                    self.scheduler.add_job(
                        self._send_user_digest,
                        CronTrigger(hour=hour, minute=minute),
                        args=[user.chat_id],
                        id=job_id,
                        name=f"Дайджест для {user.chat_id} в {hour}:{minute:02d}",
                        replace_existing=True
                    )
                    
                    logger.info(f"✅ Джоб {job_id} добавлен для chat_id {user.chat_id}")
                    
                except Exception as e:
                    logger.error(f"Ошибка при добавлении джоба для пользователя {user.chat_id}: {e}")
                    
        except Exception as e:
            logger.error(f"Ошибка при загрузке расписаний: {e}")
    
    def update_user_schedule(self, chat_id: str, digest_schedule: str):
        """Обновить расписание пользователя"""
        try:
            logger.info(f"Обновление расписания для chat_id {chat_id} на время {digest_schedule}")
            
            # Обновляем в базе данных
            db = next(get_db())
            user = db.query(User).filter(User.chat_id == chat_id).first()
            
            if user:
                user.digest_schedule = digest_schedule
                db.commit()
                logger.info(f"✅ Расписание обновлено в базе для chat_id {chat_id}")
            else:
                logger.error(f"❌ Пользователь с chat_id {chat_id} не найден")
                return False
            
            # Обновляем задачу в планировщике
            time_parts = digest_schedule.split(':')
            hour = int(time_parts[0])
            minute = int(time_parts[1])
            
            job_id = f"user_digest_{chat_id}"
            
            # Удаляем старую задачу если есть
            try:
                self.scheduler.remove_job(job_id)
                logger.info(f"Удален старый джоб {job_id}")
            except:
                pass
            
            # Добавляем новую задачу
            self.scheduler.add_job(
                self._send_user_digest,
                CronTrigger(hour=hour, minute=minute),
                args=[chat_id],
                id=job_id,
                name=f"Дайджест для {chat_id} в {hour}:{minute:02d}",
                replace_existing=True
            )
            
            logger.info(f"✅ Новый джоб {job_id} добавлен для chat_id {chat_id} в {hour}:{minute:02d}")
            return True
            
        except Exception as e:
            logger.error(f"Ошибка при обновлении расписания для {chat_id}: {e}")
            return False
    
    async def _send_daily_digest(self):
        """Отправить ежедневный дайджест всем пользователям"""
        logger.info("🕘 Запуск ежедневного дайджеста в 9:00")
        
        try:
            db = next(get_db())
            users = db.query(User).all()
            
            logger.info(f"Отправка дайджеста {len(users)} пользователям")
            
            for user in users:
                try:
                    await self._send_digest_to_user(user.chat_id)
                except Exception as e:
                    logger.error(f"Ошибка при отправке дайджеста пользователю {user.chat_id}: {e}")
                    
        except Exception as e:
            logger.error(f"Ошибка при отправке ежедневного дайджеста: {e}")
    
    async def _send_user_digest(self, chat_id: str):
        """Отправить дайджест конкретному пользователю"""
        logger.info(f"🕘 Запуск дайджеста для пользователя {chat_id}")
        
        try:
            await self._send_digest_to_user(chat_id)
            logger.info(f"✅ Дайджест успешно отправлен пользователю {chat_id}")
        except Exception as e:
            logger.error(f"❌ Ошибка при отправке дайджеста пользователю {chat_id}: {e}")
    
    async def _send_digest_to_user(self, chat_id: str):
        """Отправить дайджест пользователю"""
        try:
            logger.info(f"📡 Получение данных для дайджеста пользователя {chat_id}")
            
            # Получаем очереди пользователя
            db = next(get_db())
            user = db.query(User).filter(User.chat_id == chat_id).first()
            
            if not user:
                logger.error(f"Пользователь {chat_id} не найден в базе")
                return
            
            user_queues = db.query(Queue).filter(Queue.user_id == user.id).all()
            
            if not user_queues:
                logger.info(f"У пользователя {chat_id} нет добавленных очередей")
                return
            
            logger.info(f"Найдено {len(user_queues)} очередей для пользователя {chat_id}")
            
            # Отправляем дайджест для каждой очереди
            for queue in user_queues:
                try:
                    logger.info(f"Генерация дайджеста для очереди {queue.queue_key}")
                    
                    digest = await self.digest_service.generate_digest(
                        user_id=user.id,
                        queue_key=queue.queue_key,
                        since_hours=24
                    )
                    
                    if digest:
                        # Отправляем через Telegram бота
                        await self.telegram_bot.application.bot.send_message(
                            chat_id=chat_id,
                            text=digest,
                            parse_mode='HTML'
                        )
                        logger.info(f"✅ Дайджест отправлен для очереди {queue.queue_key}")
                    else:
                        logger.warning(f"Пустой дайджест для очереди {queue.queue_key}")
                        
                except Exception as e:
                    logger.error(f"Ошибка при генерации дайджеста для очереди {queue.queue_key}: {e}")
                    
        except Exception as e:
            logger.error(f"Ошибка при отправке дайджеста пользователю {chat_id}: {e}")
    
    def get_jobs_info(self):
        """Получить информацию о всех задачах"""
        jobs = self.scheduler.get_jobs()
        logger.info(f"Всего задач в планировщике: {len(jobs)}")
        
        for job in jobs:
            logger.info(f"Джоб: {job.id} - {job.name} - Следующий запуск: {job.next_run_time}")
        
        return jobs
    
    def stop(self):
        """Остановить планировщик"""
        logger.info("Остановка планировщика дайджестов...")
        if self.scheduler.running:
            self.scheduler.shutdown()
            logger.info("Планировщик дайджестов остановлен") 