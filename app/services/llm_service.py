"""
Основной LLM-сервис с поддержкой провайдеров и промтов
"""

import logging
import json
from typing import Dict, Any, List, Optional
from app.config import settings
from app.prompts import PromptLoader
from app.services.llm.ollama_provider import OllamaProvider

logger = logging.getLogger(__name__)


class LLMService:
    """Основной сервис для работы с LLM"""
    
    def __init__(self):
        """Инициализация LLM-сервиса"""
        self.prompt_loader = PromptLoader()
        
        # Инициализируем провайдеры
        self.providers: Dict[str, Any] = {}
        self._init_providers()
        
        # Определяем активный провайдер
        self.active_provider = settings.LLM_PROVIDER
        if self.active_provider not in self.providers:
            logger.warning(f"Провайдер {self.active_provider} не найден, используем ollama")
            self.active_provider = "ollama"
        
        logger.info(f"LLM-сервис инициализирован, активный провайдер: {self.active_provider}")
    
    def _init_providers(self):
        """Инициализация доступных провайдеров"""
        # Ollama провайдер
        ollama_config = {
            'base_url': settings.OLLAMA_BASE_URL,
            'model': settings.OLLAMA_MODEL,
            'timeout': 300  # Увеличенный таймаут для стабильной работы
        }
        self.providers['ollama'] = OllamaProvider(ollama_config)
        
        # В будущем здесь можно добавить другие провайдеры
        # self.providers['openai'] = OpenAIProvider(openai_config)
        # self.providers['gigachat'] = GigaChatProvider(gigachat_config)
    
    async def generate(self, prompt: str, **kwargs) -> str:
        """
        Генерировать ответ через активный провайдер
        
        Args:
            prompt: Промт для генерации
            **kwargs: Дополнительные параметры
            
        Returns:
            Сгенерированный ответ
        """
        provider = self.providers.get(self.active_provider)
        if not provider:
            raise ValueError(f"Провайдер {self.active_provider} не найден")
        
        return await provider.generate(prompt, **kwargs)
    
    async def create_task(self, user_text: str, available_queues: List[str], available_priorities: List[str]) -> Dict[str, Any]:
        """
        Создать задачу на основе текста пользователя
        
        Args:
            user_text: Текст пользователя
            available_queues: Список доступных очередей
            available_priorities: Список доступных приоритетов
            
        Returns:
            Словарь с данными задачи
        """
        available_queues = available_queues if available_queues else []
        available_priorities = available_priorities if available_priorities else ["Низкий", "Средний", "Высокий"]
        try:
            # Загружаем промт для создания задачи
            prompt = self.prompt_loader.load_prompt(
                'create_task.md',
                user_text=user_text,
                available_queues=available_queues,
                available_priorities=available_priorities
            )
            
            # Генерируем ответ
            response = await self.generate(prompt)
            
            # Парсим JSON из ответа
            return self._parse_json_response(response)
                
        except Exception as e:
            logger.error(f"Ошибка при создании задачи: {e}")
            return self._create_fallback_task(user_text, available_queues, available_priorities)
    
    async def analyze_intent(self, user_text: str, available_queues: List[str], available_priorities: List[str]) -> Dict[str, Any]:
        """
        Анализировать намерение пользователя
        
        Args:
            user_text: Текст пользователя
            available_queues: Список доступных очередей
            available_priorities: Список доступных приоритетов
            
        Returns:
            Словарь с результатом анализа
        """
        available_queues = available_queues if available_queues else []
        available_priorities = available_priorities if available_priorities else ["Низкий", "Средний", "Высокий"]
        try:
            # Загружаем промт для анализа намерений
            prompt = self.prompt_loader.load_prompt(
                'analyze_intent.md',
                user_text=user_text,
                available_queues=available_queues,
                available_priorities=available_priorities
            )
            
            # Генерируем ответ
            response = await self.generate(prompt)
            
            # Парсим JSON из ответа
            return self._parse_json_response(response)
            
        except Exception as e:
            logger.error(f"Ошибка при анализе намерений: {e}")
            return self._create_fallback_intent_analysis(user_text, available_queues, available_priorities)
    
    async def create_queue_summary(self, queue_data: Dict[str, Any]) -> str:
        """
        Создать дайджест очереди
        
        Args:
            queue_data: Данные очереди
            
        Returns:
            Текст дайджеста
        """
        try:
            # Загружаем промт для дайджеста
            prompt = self.prompt_loader.load_prompt(
                'queue_summary.md',
                queue_name=queue_data.get('name', 'Неизвестная очередь'),
                total_issues=queue_data.get('total_issues', 0),
                in_progress=queue_data.get('in_progress', 0),
                completed=queue_data.get('completed', 0),
                overdue=queue_data.get('overdue', 0),
                recent_issues=queue_data.get('recent_issues', []),
                priority_stats=queue_data.get('priority_stats', {})
            )
            
            # Генерируем дайджест
            return await self.generate(prompt)
                    
        except Exception as e:
            logger.error(f"Ошибка при создании дайджеста: {e}")
            return self._create_fallback_summary(queue_data)
    
    async def create_changes_summary(self, queue_data: Dict[str, Any]) -> str:
        """
        Создать резюме изменений относительно последнего дайджеста
        
        Args:
            queue_data: Данные очереди с изменениями
            
        Returns:
            Текст резюме изменений
        """
        try:
            # Загружаем промт для анализа изменений
            prompt = self.prompt_loader.load_prompt(
                'changes_summary.md',
                queue_key=queue_data.get('queue_key', 'Неизвестная очередь'),
                total_issues=queue_data.get('total_issues', 0),
                status_groups=queue_data.get('status_groups', {}),
                last_digest_time=queue_data.get('last_digest_time'),
                current_time=queue_data.get('current_time')
            )
            
            # Генерируем резюме
            return await self.generate(prompt)
                    
        except Exception as e:
            logger.error(f"Ошибка при создании резюме изменений: {e}")
            return "Обнаружены изменения в задачах."

    async def analyze_task_creation_intent(self, user_text: str, available_queues: List[str]) -> Dict[str, Any]:
        """
        Анализировать намерение создания задачи
        
        Args:
            user_text: Текст пользователя
            available_queues: Список доступных очередей
            
        Returns:
            Словарь с результатом анализа намерений
        """
        available_queues = available_queues if available_queues else []
        available_priorities = ["Низкий", "Средний", "Высокий", "Критический"]
        
        try:
            # Загружаем промт для анализа намерений
            prompt = self.prompt_loader.load_prompt(
                'analyze_intent.md',
                user_text=user_text,
                available_queues=available_queues,
                available_priorities=available_priorities
            )
            
            # Генерируем ответ
            response = await self.generate(prompt)
            
            # Парсим JSON из ответа
            return self._parse_json_response(response)
            
        except Exception as e:
            logger.error(f"Ошибка при анализе намерений создания задачи: {e}")
            return self._create_fallback_intent_analysis(user_text, available_queues, available_priorities)

    async def analyze_free_conversation(self, user_message: str, available_queues: List[str], available_priorities: List[str], user_context: str = "") -> Dict[str, Any]:
        """
        Анализировать свободное сообщение пользователя и определять намерения
        
        Args:
            user_message: Сообщение пользователя
            available_queues: Список доступных очередей
            available_priorities: Список доступных приоритетов
            user_context: Контекст пользователя (предыдущие сообщения, настройки)
            
        Returns:
            Словарь с анализом намерений и данными для действий
        """
        available_queues = available_queues or []
        available_priorities = available_priorities or ["Низкий", "Средний", "Высокий", "Критический"]
        try:
            # Загружаем промт для свободного общения
            prompt = self.prompt_loader.load_prompt(
                'free_conversation.md',
                user_message=user_message,
                available_queues=available_queues,
                available_priorities=available_priorities,
                user_context=user_context
            )
            
            # Генерируем ответ
            response = await self.generate(prompt)
            
            # Парсим JSON из ответа
            return self._parse_json_response(response)
            
        except Exception as e:
            logger.error(f"Ошибка при анализе свободного общения: {e}")
            return self._create_fallback_conversation_analysis(user_message, available_queues, available_priorities)

    def _parse_json_response(self, response: str) -> Dict[str, Any]:
        """
        Парсить JSON из ответа LLM
        
        Args:
            response: Ответ от LLM
            
        Returns:
            Распарсенный JSON
        """
        try:
            # Ищем JSON в ответе
            json_start = response.find('{')
            json_end = response.rfind('}') + 1
            
            if json_start != -1 and json_end != 0:
                json_str = response[json_start:json_end]
                return json.loads(json_str)
            else:
                raise ValueError("JSON не найден в ответе")
                
        except json.JSONDecodeError as e:
            logger.error(f"Ошибка парсинга JSON: {e}")
            raise
    
    def _create_fallback_task(self, user_text: str, available_queues: List[str],
                            available_priorities: List[str] = None) -> Dict[str, Any]:
        """Fallback для создания задачи"""
        return {
            "summary": user_text[:100],
            "description": user_text,
            "queue": available_queues[0] if available_queues else None,
            "priority": "Средний",
            "assignee": None,
            "deadline": None,
            "tags": None,
            "type": "task"
        }
        
    def _create_fallback_intent_analysis(self, user_text: str, available_queues: List[str],
                                       available_priorities: List[str] = None) -> Dict[str, Any]:
        """Fallback для анализа намерений"""
        return {
            "wants_to_create_task": False,
            "has_sufficient_data": False,
            "extracted_data": {},
            "missing_data": [],
            "confidence": 0.5,
            "reasoning": "Fallback анализ"
        }
    
    def _create_fallback_summary(self, queue_data: Dict[str, Any]) -> str:
        """Fallback для дайджеста"""
        return f"📊 Дайджест очереди '{queue_data.get('name', 'Неизвестная')}'\n\nНе удалось создать дайджест."
    
    def _create_fallback_conversation_analysis(self, user_message: str, available_queues: List[str],
                                             available_priorities: List[str] = None) -> Dict[str, Any]:
        """Fallback для анализа свободного общения"""
        message_lower = user_message.lower()
        
        # Простая эвристика для определения намерений
        if any(word in message_lower for word in ['создай', 'добавь', 'новая', 'задача', 'баг', 'ошибка']):
            return {
                "intent": "create_task",
                "action": "create_task",
                "confidence": 0.7,
                "response": "🤖 Понял, создаю задачу. Пожалуйста, опишите подробнее что нужно сделать.",
                "data": {
                    "queue_key": available_queues[0] if available_queues else None,
                    "task_data": {
                        "summary": None,
                        "description": None,
                        "priority": "Средний",
                        "assignee": None
                    },
                    "schedule_time": None,
                    "digest_request": False
                }
            }
        elif any(word in message_lower for word in ['дайджест', 'статус', 'отчет', 'что происходит']):
            return {
                "intent": "get_digest",
                "action": "show_digest",
                "confidence": 0.8,
                "response": "📊 Сейчас покажу дайджест по проекту...",
                "data": {
                    "queue_key": None,
                    "task_data": None,
                    "schedule_time": None,
                    "digest_request": True
                }
            }
        else:
            return {
                "intent": "general_question",
                "action": "help",
                "confidence": 0.5,
                "response": "🤖 Не совсем понял, что вы хотите. Попробуйте:\n• Создать задачу\n• Показать дайджест\n• Установить расписание\n• Показать очереди",
                "data": {
                    "queue_key": None,
                    "task_data": None,
                    "schedule_time": None,
                    "digest_request": False
                }
            }
    
    def get_provider_info(self) -> Dict[str, Any]:
        """Получить информацию о провайдерах"""
        return {
            "active_provider": self.active_provider,
            "providers": {name: provider.get_info() for name, provider in self.providers.items()}
        }
    
    async def health_check(self) -> Dict[str, Any]:
        """Проверить здоровье всех провайдеров"""
        health_status = {}
        
        for name, provider in self.providers.items():
            try:
                is_healthy = await provider.health_check()
                health_status[name] = {
                    "available": provider.is_available(),
                    "healthy": is_healthy
                }
            except Exception as e:
                logger.error(f"Ошибка health check для {name}: {e}")
                health_status[name] = {
                    "available": False,
                    "healthy": False,
                    "error": str(e)
                }
        
        return health_status
    
    async def classify_status(self, original_status: str) -> str:
        """
        Классифицировать статус задачи через LLM
        
        Args:
            original_status: Исходный статус из Yandex Tracker
            
        Returns:
            Стандартизированный статус: Новые, В работе, На проверке, Завершена, Отменена
        """
        try:
            # Загружаем промт для классификации статусов
            prompt = self.prompt_loader.load_prompt(
                'status_classification.md',
                status=original_status,
                description=""
            )
            
            # Генерируем классификацию
            response = await self.generate(prompt)
            
            # Парсим JSON ответ
            result = self._parse_json_response(response)
            if isinstance(result, dict) and 'normalized_status' in result:
                return result['normalized_status']
            elif isinstance(result, str):
                return result
            else:
                logger.warning(f"LLM вернул неожиданный формат: '{response}', используем 'Новые'")
                return 'Новые'
            
        except Exception as e:
            logger.error(f"Ошибка при классификации статуса '{original_status}': {e}")
            # Fallback на старую логику
            return self._fallback_classify_status(original_status)
    
    def _fallback_classify_status(self, status: str) -> str:
        """Fallback классификация статуса (старая логика)"""
        status_lower = status.lower()
        
        if any(word in status_lower for word in ['done', 'готово', 'complete', 'завершено', 'решено', 'resolved', 'closed', 'закрыто', 'выполнено', 'готов']):
            return 'Завершена'
        elif any(word in status_lower for word in ['review', 'тест', 'testing', 'проверка', 'ревью', 'code review']):
            return 'На проверке'
        elif any(word in status_lower for word in ['progress', 'в работе', 'in progress', 'работа', 'выполняется', 'в процессе', 'разработка', 'открытая', 'открыта', 'open']):
            return 'В работе'
        elif any(word in status_lower for word in ['blocked', 'блок', 'block', 'блокировано', 'заблокировано', 'требуется информация', 'information required', 'need info', 'info needed']):
            return 'Отменена'
        else:
            return 'Новые'
    
    async def ensure_llm_models(self):
        """Проверить и при необходимости загрузить все нужные LLM-модели"""
        for name, provider in self.providers.items():
            if hasattr(provider, 'ensure_model_available'):
                await provider.ensure_model_available()
        return None 