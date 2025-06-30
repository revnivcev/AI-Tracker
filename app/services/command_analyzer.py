import logging
import json
import re
import time
from typing import Dict, Any, Optional, List
from app.services.llm_service import LLMService
from app.models.user import User
from app.models.queue import Queue
from app.models.database import get_db

logger = logging.getLogger(__name__)


class CommandAnalyzer:
    def __init__(self, llm_service: LLMService):
        self.llm_service = llm_service
        # Контекстная память для улучшения понимания
        self.conversation_context = {}
        
    async def analyze_text(self, text: str, user_id: int) -> Dict[str, Any]:
        """Анализировать текст и определять команду с многоуровневым анализом"""
        try:
            text_lower = text.lower().strip()
            chat_id = str(user_id)
            
            logger.info(f"Анализируем сообщение от {chat_id}: {text[:50]}...")
            
            # 1. Проверяем точные совпадения (быстрый путь)
            exact_match = self._check_exact_matches(text_lower)
            if exact_match and exact_match.get("confidence", 0) > 0.8:
                logger.info(f"Найдено точное совпадение: {exact_match['command']}")
                return exact_match

            # 2. Проверяем контекст предыдущих сообщений
            context_match = self._check_context_continuation(chat_id, text_lower)
            if context_match:
                logger.info(f"Найдено контекстное продолжение: {context_match['command']}")
                return context_match

            # 3. Анализируем намерение создания задачи с помощью LLM
            task_intent = await self._analyze_task_creation_intent(text, chat_id)
            if task_intent and task_intent.get("wants_to_create_task", False):
                logger.info(f"LLM определил намерение создать задачу: {task_intent}")
                return task_intent

            # 4. Fallback анализ с эвристиками
            fallback_result = self._fallback_analysis(text_lower, chat_id)
            logger.info(f"Fallback анализ: {fallback_result['command']}")
            return fallback_result
            
        except Exception as e:
            logger.error(f"Ошибка при анализе текста: {e}")
            return self._create_unknown_response()

    def _check_exact_matches(self, text: str) -> Optional[Dict[str, Any]]:
        """Проверить точные совпадения команд с улучшенными паттернами"""
        
        # Core-функция: Дайджесты (высокий приоритет)
        digest_patterns = [
            r'\b(дайджест|отчет|сводка|статус|что сделано|покажи задачи|покажи работу|отчет по задачам)\b',
            r'\b(как дела|что нового|обновления|изменения)\b'
        ]
        
        # Beta-функция: Создание задач
        create_task_patterns = [
            r'\b(создай|создать|добавь|добавить)\s+(задачу|тикет|issue)\b',
            r'\b(новая задача|новый тикет)\b'
        ]
        
        # Beta-функция: Расписание
        schedule_patterns = [
            r'\b(расписание|время дайджеста|когда дайджест|изменить время|настроить время)\b',
            r'\b(установи|поставь)\s+(время|расписание)\b'
        ]
        
        # Core-функция: Очереди
        queues_patterns = [
            r'\b(очереди|список очередей|покажи очереди|доступные очереди|какие очереди)\b',
            r'\b(проекты|список проектов)\b'
        ]

        # Проверяем дайджест (core-функция)
        for pattern in digest_patterns:
            if re.search(pattern, text):
                return {
                    "command": "send_digest",
                    "confidence": 0.95,
                    "needs_clarification": False,
                    "feature_status": "core",
                    "data": {},
                    "clarification_questions": []
                }

        # Проверяем создание задачи (beta-функция)
        for pattern in create_task_patterns:
            if re.search(pattern, text):
                return {
                    "command": "create_task",
                    "confidence": 0.85,
                    "needs_clarification": True,
                    "feature_status": "beta",
                    "data": {},
                    "clarification_questions": [
                        "🤖 Beta-функция: Создание задач\n"
                        "В какой очереди создать задачу?\n"
                        "Опишите задачу подробнее."
                    ]
                }

        # Проверяем расписание (beta-функция)
        for pattern in schedule_patterns:
            if re.search(pattern, text):
                return {
                    "command": "set_schedule",
                    "confidence": 0.8,
                    "needs_clarification": True,
                    "feature_status": "beta",
                    "data": {},
                    "clarification_questions": [
                        "⏰ Beta-функция: Настройка расписания\n"
                        "В какое время отправлять дайджест? (формат HH:MM, например 09:00)"
                    ]
                }

        # Проверяем очереди (core-функция)
        for pattern in queues_patterns:
            if re.search(pattern, text):
                return {
                    "command": "show_queues",
                    "confidence": 0.9,
                    "needs_clarification": False,
                    "feature_status": "core",
                    "data": {},
                    "clarification_questions": []
                }

        return None

    def _check_context_continuation(self, chat_id: str, text: str) -> Optional[Dict[str, Any]]:
        """Проверить продолжение контекста предыдущих сообщений"""
        if chat_id not in self.conversation_context:
            return None
            
        context = self.conversation_context[chat_id]
        last_command = context.get("last_command")
        
        # Если последняя команда была create_task, проверяем описание
        if last_command == "create_task" and len(text.split()) > 3:
            return {
                "command": "create_task",
                "confidence": 0.7,
                "needs_clarification": False,
                "feature_status": "beta",
                "data": {"description": text},
                "clarification_questions": []
            }
            
        # Если последняя команда была set_schedule, проверяем время
        if last_command == "set_schedule":
            time_match = re.search(r'(\d{1,2}):(\d{2})', text)
            if time_match:
                return {
                    "command": "set_schedule",
                    "confidence": 0.8,
                    "needs_clarification": False,
                    "feature_status": "beta",
                    "data": {"time": f"{time_match.group(1)}:{time_match.group(2)}"},
                    "clarification_questions": []
                }
        
        return None

    def _fallback_analysis(self, text: str, chat_id: str) -> Dict[str, Any]:
        """Fallback анализ с эвристиками"""
        
        # Эвристика 1: Если текст содержит время, вероятно это расписание
        if re.search(r'\d{1,2}:\d{2}', text):
            return {
                "command": "set_schedule",
                "confidence": 0.6,
                "needs_clarification": False,
                "feature_status": "beta",
                "data": {},
                "clarification_questions": []
            }
        
        # Эвристика 2: Если текст длинный и содержит технические термины, вероятно создание задачи
        if len(text.split()) > 5 and any(word in text for word in ['баг', 'ошибка', 'исправить', 'добавить', 'сделать']):
            return {
                "command": "create_task",
                "confidence": 0.5,
                "needs_clarification": True,
                "feature_status": "beta",
                "data": {},
                "clarification_questions": [
                    "🤖 Beta-функция: Создание задач\n"
                    "Похоже, вы хотите создать задачу. В какой очереди?"
                ]
            }
        
        # Эвристика 3: Если текст короткий и содержит вопросительные слова
        if len(text.split()) <= 3 and any(word in text for word in ['что', 'как', 'когда', 'где']):
            return {
                "command": "send_digest",
                "confidence": 0.4,
                "needs_clarification": False,
                "feature_status": "core",
                "data": {},
                "clarification_questions": []
            }
        
        return self._create_unknown_response()

    def _create_unknown_response(self) -> Dict[str, Any]:
        """Создать ответ для неизвестной команды"""
        return {
            "command": "unknown",
            "confidence": 0.3,
            "needs_clarification": True,
            "feature_status": "unknown",
            "data": {},
            "clarification_questions": [
                "❓ Не понял команду. Попробуйте:\n"
                "📊 /send_now - получить дайджест (core-функция)\n"
                "📋 /create_task - создать задачу (beta-функция)\n"
                "⏰ /set_schedule - настроить расписание (beta-функция)\n"
                "📁 /show_available_queues - показать очереди (core-функция)\n"
                "❓ /help - полная справка"
            ]
        }

    def update_context(self, chat_id: str, command: str, data: Dict[str, Any] = None):
        """Обновить контекст разговора"""
        if chat_id not in self.conversation_context:
            self.conversation_context[chat_id] = {}
        
        self.conversation_context[chat_id].update({
            "last_command": command,
            "last_data": data or {},
            "timestamp": time.time()
        })

    def get_clarification_questions(self, command: str, feature_status: str = "core") -> List[str]:
        """Получить вопросы для уточнения команды с учетом статуса функции"""
        base_questions = {
            "create_task": [
                "🤖 Beta-функция: Создание задач\n"
                "В какой очереди создать задачу?\n"
                "Опишите задачу подробнее."
            ],
            "set_schedule": [
                "⏰ Beta-функция: Настройка расписания\n"
                "В какое время отправлять дайджест? (формат HH:MM, например 09:00)"
            ],
            "unknown": [
                "❓ Не понял команду. Попробуйте:\n"
                "📊 /send_now - получить дайджест (core-функция)\n"
                "📋 /create_task - создать задачу (beta-функция)\n"
                "⏰ /set_schedule - настроить расписание (beta-функция)\n"
                "📁 /show_available_queues - показать очереди (core-функция)\n"
                "❓ /help - полная справка"
            ]
        }
        
        return base_questions.get(command, ["Не понял команду. Попробуйте использовать /help для списка команд."])

    async def _analyze_task_creation_intent(self, text: str, chat_id: str) -> Optional[Dict[str, Any]]:
        """Анализировать намерение создания задачи с помощью LLM"""
        try:
            # Получаем доступные очереди из базы данных
            db = next(get_db())
            user = db.query(User).filter(User.chat_id == chat_id).first()
            if not user:
                return None
            
            user_queues = db.query(Queue).filter(Queue.user_id == user.id).all()
            available_queues = [queue.queue_key for queue in user_queues]
            
            if not available_queues:
                return None
            
            # Анализируем намерение с помощью LLM
            intent_result = await self.llm_service.analyze_task_creation_intent(text, available_queues)
            
            if intent_result.get("wants_to_create_task", False):
                # Добавляем информацию о рефакторинге
                text_refactoring = intent_result.get("text_refactoring", {})
                extracted_data = intent_result.get("extracted_data", {})
                
                if intent_result.get("has_sufficient_data", False):
                    # Достаточно данных - создаем задачу сразу
                    return {
                        "command": "create_task",
                        "confidence": intent_result.get("confidence", 0.8),
                        "needs_clarification": False,
                        "feature_status": "beta",
                        "data": {
                            **extracted_data,
                            "refactored_text": text_refactoring.get("improved", text),
                            "original_text": text_refactoring.get("original", text),
                            "refactoring_changes": text_refactoring.get("changes", [])
                        },
                        "clarification_questions": []
                    }
                else:
                    # Недостаточно данных - запрашиваем уточнения
                    missing_data = intent_result.get("missing_data", [])
                    clarification_text = "🤖 Beta-функция: Создание задач\n"
                    
                    # Показываем улучшенную версию текста, если есть
                    if text_refactoring.get("improved") and text_refactoring.get("improved") != text:
                        clarification_text += f"💡 Улучшенная версия: {text_refactoring['improved']}\n\n"
                    
                    if missing_data:
                        clarification_text += f"Недостает: {', '.join(missing_data)}\n"
                    clarification_text += "Опишите задачу подробнее."
                    
                    return {
                        "command": "create_task",
                        "confidence": intent_result.get("confidence", 0.7),
                        "needs_clarification": True,
                        "feature_status": "beta",
                        "data": {
                            **extracted_data,
                            "refactored_text": text_refactoring.get("improved", text),
                            "original_text": text_refactoring.get("original", text),
                            "refactoring_changes": text_refactoring.get("changes", [])
                        },
                        "clarification_questions": [clarification_text]
                    }
            
            return None
            
        except Exception as e:
            logger.error(f"Ошибка при анализе намерения создания задачи: {e}")
            return None 