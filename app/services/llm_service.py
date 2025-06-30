import logging
import httpx
import json
import asyncio
from typing import Dict, List, Optional, Any
from app.config import settings

logger = logging.getLogger(__name__)

# Простое кэширование для ускорения повторных запросов
_response_cache = {}

class LLMService:
    def __init__(self):
        self.provider = settings.LLM_PROVIDER
        self.ollama_base_url = settings.OLLAMA_BASE_URL
        self.ollama_model = settings.OLLAMA_MODEL
        self.gigachat_api_key = settings.GIGACHAT_API_KEY
        self.gigachat_auth_url = settings.GIGACHAT_AUTH_URL
        self.base_url = settings.OLLAMA_BASE_URL
        self.model = settings.OLLAMA_MODEL
        self.timeout = 60  # Увеличиваем таймаут

    def _get_cache_key(self, prompt: str, model: str) -> str:
        """Генерирует ключ кэша для промпта"""
        return f"{model}:{hash(prompt)}"
    
    def _get_cached_response(self, prompt: str, model: str) -> Optional[str]:
        """Получает кэшированный ответ"""
        cache_key = self._get_cache_key(prompt, model)
        return _response_cache.get(cache_key)
    
    def _cache_response(self, prompt: str, model: str, response: str):
        """Кэширует ответ"""
        cache_key = self._get_cache_key(prompt, model)
        _response_cache[cache_key] = response
        # Ограничиваем размер кэша
        if len(_response_cache) > 100:
            # Удаляем старые записи
            old_keys = list(_response_cache.keys())[:20]
            for key in old_keys:
                del _response_cache[key]

    async def generate_digest_summary(self, issues: List[Dict[str, Any]]) -> str:
        """Генерировать краткое резюме изменений для дайджеста в стиле daily standup"""
        if not issues:
            return "Нет изменений в задачах за этот период."

        # Группируем задачи по статусу
        status_groups = {}
        users_involved = set()
        
        for issue in issues:
            status = issue.get('status', 'Unknown')
            if status not in status_groups:
                status_groups[status] = []
            status_groups[status].append(issue)
            
            # Собираем пользователей
            assignee = issue.get('assignee', 'Unassigned')
            if assignee != 'Unassigned':
                users_involved.add(assignee)

        # Формируем текст для анализа
        issues_text = ""
        for status, status_issues in status_groups.items():
            issues_text += f"\n{status}:\n"
            for issue in status_issues:
                assignee = issue.get('assignee', 'Unassigned')
                issues_text += f"- {issue['key']}: {issue['summary']} (Исполнитель: {assignee})\n"

        prompt = f"""
Ты - помощник для создания Daily Scrum дайджеста. Создай краткое резюме изменений в задачах.

Данные о задачах:
{issues_text}

Общее количество задач: {len(issues)}

Создай краткое резюме в стиле Daily Standup (2-3 предложения), включая:
1. Что было сделано (статус Done/In Progress)
2. Что планируется (статус To Do)
3. Какие проблемы возникли (статус Blocked)

Используй только реальные данные из задач. Не добавляй выдуманную информацию.
"""

        try:
            logger.info(f"Генерируем резюме для {len(issues)} задач")
            logger.info(f"Промпт: {prompt[:200]}...")
            response = await self._call_llm(prompt)
            logger.info(f"Получен ответ от LLM: {response[:200]}...")
            return response.strip()
        except Exception as e:
            logger.error(f"Ошибка при генерации резюме дайджеста: {e}")
            # Возвращаем fallback с информацией о пользователях
            fallback = f"Обнаружены изменения в {len(issues)} задачах. "
            if users_involved:
                fallback += f"Задействованные участники: {', '.join(users_involved)}. "
            
            # Добавляем краткую сводку по статусам
            for status, status_issues in status_groups.items():
                if status_issues:
                    fallback += f"{status}: {len(status_issues)} задач. "
            
            return fallback

    async def parse_issue_description(self, description: str) -> Dict[str, Any]:
        """Парсить описание задачи для создания структурированной задачи"""
        try:
            prompt = f"""
Ты - помощник для создания задач в Yandex Tracker. Проанализируй описание и создай структурированную задачу.

Описание: {description}

Создай JSON с полями:
- summary: краткое название задачи (максимум 100 символов)
- description: подробное описание
- priority: приоритет (Low, Medium, High, Critical)
- assignee: исполнитель (если указан)

Пример ответа:
{{
    "summary": "Краткое название",
    "description": "Подробное описание задачи",
    "priority": "Medium",
    "assignee": "Имя исполнителя"
}}

Отвечай только JSON без дополнительного текста.
"""

            response = await self._call_llm(prompt)
            
            try:
                # Пытаемся парсить JSON
                parsed = json.loads(response)
                return {
                    "summary": parsed.get("summary", description[:100]),
                    "description": parsed.get("description", description),
                    "priority": parsed.get("priority", "Medium"),
                    "assignee": parsed.get("assignee")
                }
            except json.JSONDecodeError:
                # Если JSON не парсится, используем fallback
                return {
                    "summary": description[:100],
                    "description": description,
                    "priority": "Medium",
                    "assignee": None
                }
                
        except Exception as e:
            logger.error(f"Ошибка при парсинге описания задачи: {e}")
            return {
                "summary": description[:100],
                "description": description,
                "priority": "Medium",
                "assignee": None
            }

    def _fix_json_response(self, json_str: str) -> Optional[str]:
        """Попытаться исправить некорректный JSON"""
        try:
            # Убираем лишние символы
            json_str = json_str.strip()
            
            # Заменяем одинарные кавычки на двойные
            json_str = json_str.replace("'", '"')
            
            # Исправляем null значения
            json_str = json_str.replace('"null"', 'null')
            
            # Убираем лишние запятые
            json_str = json_str.replace(',}', '}')
            json_str = json_str.replace(',]', ']')
            
            return json_str
        except Exception as e:
            logger.error(f"Ошибка при исправлении JSON: {e}")
            return None

    async def _call_ollama_api(self, prompt: str) -> str:
        """Вызов Ollama API (всегда через /api/generate) с кэшированием"""
        try:
            # Проверяем кэш
            cached_response = self._get_cached_response(prompt, self.model)
            if cached_response:
                logger.info("Используем кэшированный ответ")
                return cached_response
            
            logger.info(f"Вызываем Ollama API с моделью: {self.model}")
            logger.info(f"URL: {self.base_url}/api/generate")
            logger.info(f"Промпт (первые 100 символов): {prompt[:100]}...")
            
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.base_url}/api/generate",
                    json={
                        "model": self.model,
                        "prompt": prompt,
                        "stream": False,
                        "options": {
                            "temperature": 0.7,
                            "top_p": 0.9
                        }
                    }
                )
                
                if response.status_code == 200:
                    result = response.json()
                    response_text = result.get("response", "").strip()
                    
                    # Кэшируем ответ
                    self._cache_response(prompt, self.model, response_text)
                    
                    logger.info(f"Ollama ответ получен, длина: {len(response_text)} символов")
                    return response_text
                else:
                    logger.error(f"Ошибка API: {response.status_code} - {response.text}")
                    return ""
                    
        except Exception as e:
            logger.error(f"Ошибка при вызове Ollama API: {e}")
            return ""

    async def _call_gigachat(self, prompt: str) -> str:
        """Вызов GigaChat API"""
        if not self.gigachat_api_key:
            raise ValueError("GigaChat API key не настроен")

        async with httpx.AsyncClient() as client:
            # Получаем токен доступа
            auth_url = self.gigachat_auth_url or "https://ngw.devices.sberbank.ru:9443/api/v2/oauth"
            auth_response = await client.post(
                auth_url,
                headers={
                    "Authorization": f"Bearer {self.gigachat_api_key}",
                    "Content-Type": "application/x-www-form-urlencoded"
                },
                data={"scope": "GIGACHAT_API_PERS"},
                timeout=30.0
            )
            auth_response.raise_for_status()
            access_token = auth_response.json().get('access_token')

            # Вызываем API
            chat_response = await client.post(
                "https://gigachat.devices.sberbank.ru/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "GigaChat:latest",
                    "messages": [
                        {"role": "user", "content": prompt}
                    ],
                    "temperature": 0.7,
                    "max_tokens": 1000
                },
                timeout=30.0
            )
            chat_response.raise_for_status()
            result = chat_response.json()
            return result['choices'][0]['message']['content']

    async def _call_llm(self, prompt: str) -> str:
        """Вызвать LLM API"""
        try:
            logger.info(f"Вызываем Ollama API с моделью: {self.model}")
            logger.info(f"URL: {self.base_url}/api/generate")
            logger.info(f"Промпт (первые 100 символов): {prompt[:100]}...")

            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.base_url}/api/generate",
                    json={
                        "model": self.model,
                        "prompt": prompt,
                        "stream": False,
                        "options": {
                            "temperature": 0.7,
                            "top_p": 0.9
                        }
                    }
                )
                
                if response.status_code == 200:
                    result = response.json()
                    return result.get("response", "").strip()
                else:
                    logger.error(f"Ошибка API: {response.status_code} - {response.text}")
                    return ""
                    
        except Exception as e:
            logger.error(f"Ошибка при вызове Ollama API: {e}")
            return ""

    def is_available(self) -> bool:
        """Проверить доступность LLM сервиса"""
        if self.provider == "ollama":
            return True  # Ollama работает локально
        elif self.provider == "gigachat":
            return bool(self.gigachat_api_key)
        return False 

    async def analyze_and_create_task(self, user_text: str, available_queues: List[str], available_priorities: List[str] = None) -> Dict[str, Any]:
        """Анализировать сплошной текст и создать структурированную задачу с определением очереди"""
        
        # Если приоритеты не переданы, используем стандартные
        if not available_priorities:
            available_priorities = ["Низкий", "Средний", "Высокий", "Критический"]
        
        priority_rules = f"""
        Доступные приоритеты: {', '.join(available_priorities)}
        
        Правила определения приоритета:
        - Критический: срочные задачи, критические баги, блокеры
        - Высокий: важные задачи, баги, срочные функции
        - Средний: обычные задачи, новые функции, улучшения
        - Низкий: неважные задачи, документация, косметические изменения
        """
        
        prompt = f"""
        Ты - помощник для создания задач в Yandex Tracker. Проанализируй описание пользователя и создай структурированную задачу.

        Текст пользователя: {user_text}

        Доступные очереди: {', '.join(available_queues)}

        Создай JSON с полями:
        - summary: краткое название задачи (до 100 символов)
        - description: подробное описание задачи
        - priority: приоритет из списка доступных (определи по контексту)
        - assignee: имя исполнителя или null
        - queue: ключ очереди из списка доступных (определи по контексту задачи)
        - deadline: срок выполнения в формате YYYY-MM-DD или null
        - tags: список тегов через запятую или null

        Правила определения очереди:
        - Если задача связана с разработкой, тестированием, багами - используй очереди с названиями типа DEV, TEST, BUG
        - Если задача связана с документацией - используй очереди с названиями типа DOC, WIKI
        - Если задача связана с дизайном - используй очереди с названиями типа DESIGN, UI
        - Если не можешь определить - используй первую очередь из списка

        {priority_rules}

        Формат ответа (только JSON):
        {{
            "summary": "название",
            "description": "описание", 
            "priority": "Средний",
            "assignee": null,
            "queue": "OCHERED",
            "deadline": null,
            "tags": null
        }}

        Отвечай только JSON без дополнительного текста.
        """

        try:
            logger.info(f"Анализируем текст для создания задачи: {user_text[:50]}...")
            logger.info(f"Доступные очереди: {available_queues}")
            logger.info(f"Доступные приоритеты: {available_priorities}")
            
            response = await self._call_llm(prompt)
            logger.info(f"Получен ответ от LLM: {response}")
            
            # Извлекаем JSON из ответа
            json_start = response.find('{')
            json_end = response.rfind('}') + 1
            if json_start != -1 and json_end != 0:
                json_str = response[json_start:json_end]
                try:
                    parsed = json.loads(json_str)
                    logger.info(f"Успешно распарсено: {parsed}")
                    
                    # Валидируем результат
                    if not parsed.get('summary'):
                        raise ValueError("Отсутствует summary")
                    
                    if not parsed.get('queue') or parsed['queue'] not in available_queues:
                        # Если очередь не определена или неверная, используем первую доступную
                        parsed['queue'] = available_queues[0] if available_queues else None
                        logger.warning(f"Очередь не определена или неверная, используем: {parsed['queue']}")
                    
                    if not parsed.get('priority') or parsed['priority'] not in available_priorities:
                        # Если приоритет не определен или неверный, используем средний
                        parsed['priority'] = "Средний" if "Средний" in available_priorities else available_priorities[0] if available_priorities else "Средний"
                        logger.warning(f"Приоритет не определен или неверный, используем: {parsed['priority']}")
                    
                    return parsed
                except json.JSONDecodeError as e:
                    logger.error(f"Ошибка парсинга JSON: {e}, JSON: {json_str}")
                    # Пробуем исправить JSON
                    fixed_json = self._fix_json_response(json_str)
                    if fixed_json:
                        try:
                            parsed = json.loads(fixed_json)
                            logger.info(f"Исправленный JSON распарсен: {parsed}")
                            
                            # Валидируем результат
                            if not parsed.get('summary'):
                                raise ValueError("Отсутствует summary")
                            
                            if not parsed.get('queue') or parsed['queue'] not in available_queues:
                                parsed['queue'] = available_queues[0] if available_queues else None
                                logger.warning(f"Очередь не определена или неверная, используем: {parsed['queue']}")
                            
                            if not parsed.get('priority') or parsed['priority'] not in available_priorities:
                                parsed['priority'] = "Средний" if "Средний" in available_priorities else available_priorities[0] if available_priorities else "Средний"
                                logger.warning(f"Приоритет не определен или неверный, используем: {parsed['priority']}")
                            
                            return parsed
                        except json.JSONDecodeError:
                            pass
            
            logger.warning("Не удалось найти или распарсить JSON в ответе, используем fallback")
            # Fallback - возвращаем базовую структуру
            return {
                "summary": user_text[:100] + "..." if len(user_text) > 100 else user_text,
                "description": user_text,
                "priority": "Средний" if "Средний" in available_priorities else available_priorities[0] if available_priorities else "Средний",
                "assignee": None,
                "queue": available_queues[0] if available_queues else None,
                "deadline": None,
                "tags": None
            }
        except Exception as e:
            logger.error(f"Ошибка при анализе текста для создания задачи: {e}")
            return {
                "summary": user_text[:100] + "..." if len(user_text) > 100 else user_text,
                "description": user_text,
                "priority": "Средний" if "Средний" in available_priorities else available_priorities[0] if available_priorities else "Средний",
                "assignee": None,
                "queue": available_queues[0] if available_queues else None,
                "deadline": None,
                "tags": None
            }

    async def create_queue_summary(self, queue_data: Dict[str, Any]) -> str:
        """Создать резюме для конкретной очереди"""
        try:
            queue_key = queue_data["queue_key"]
            total_issues = queue_data["total_issues"]
            status_groups = queue_data["status_groups"]
            issues = queue_data["issues"]

            # Формируем детальное описание задач
            issues_text = ""
            for status, status_issues in status_groups.items():
                if status_issues:
                    issues_text += f"\n{status} ({len(status_issues)} задач):\n"
                    for issue in status_issues:
                        assignee = issue.get('assignee', 'Unassigned')
                        issues_text += f"- {issue['key']}: {issue['summary']} (Исполнитель: {assignee})\n"

            prompt = f"""
Ты - эксперт по анализу данных проектов. Создай объективное резюме изменений в задачах очереди {queue_key}.

ДАННЫЕ ДЛЯ АНАЛИЗА:
{issues_text}

ОБЩЕЕ КОЛИЧЕСТВО ЗАДАЧ: {total_issues}

ТРЕБОВАНИЯ К ОТВЕТУ:
1. НЕ используй фразы типа "в ходе ежедневного собрания", "в рамках Daily Scrum", "были отмечены"
2. НЕ добавляй выдуманную информацию о процессах или встречах
3. Используй ТОЛЬКО факты из предоставленных данных
4. Пиши в прошедшем времени для завершенных задач (Done)
5. Пиши в настоящем времени для текущих задач (In Progress, To Do)
6. Будь максимально конкретным и детальным
7. Объем: 4-6 предложений с деталями

СТРУКТУРА АНАЛИЗА:
1. Конкретные факты о выполненных задачах (статус Done) - 2-3 предложения
2. Текущие активные задачи (статус In Progress) - 1-2 предложения  
3. Запланированные задачи (статус To Do) - 1 предложение
4. Блокировки, если есть (статус Blocked) - 1 предложение

ПРИМЕР ПРАВИЛЬНОГО СТИЛЯ:
"За отчетный период завершены задачи по исправлению багов в модуле авторизации и оптимизации запросов к базе данных. В работе находятся задачи по миграции на новую версию фреймворка и настройке системы мониторинга. Запланированы задачи по обновлению документации API и интеграции с внешними сервисами."

Используй ТОЛЬКО реальные данные из предоставленных задач. НЕ добавляй информацию о встречах, процессах или выдуманные детали.
"""

            response = await self._call_llm(prompt)
            return response if response else "Нет изменений в задачах за этот период."
            
        except Exception as e:
            logger.error(f"Ошибка при создании резюме очереди: {e}")
            return "Нет изменений в задачах за этот период." 

    async def analyze_task_creation_intent(self, user_text: str, available_queues: List[str], available_priorities: Optional[List[str]] = None) -> Dict[str, Any]:
        """Анализировать намерение создания задачи и определять, достаточно ли данных"""
        
        # Если приоритеты не переданы, используем стандартные
        if not available_priorities:
            available_priorities = ["Низкий", "Средний", "Высокий", "Критический"]
        
        prompt = f"""
Ты - эксперт по анализу намерений пользователей для создания задач в Yandex Tracker.

Текст пользователя: {user_text}

Доступные очереди: {', '.join(available_queues)}
Доступные приоритеты: {', '.join(available_priorities)}

Проанализируй текст и определи:

1. Хочет ли пользователь создать задачу?
2. Достаточно ли информации для создания задачи?
3. Какие данные можно извлечь и отрефакторить?

ОТВЕТЬ В ФОРМАТЕ JSON:
{{
    "wants_to_create_task": true/false,
    "has_sufficient_data": true/false,
    "extracted_data": {{
        "summary": "краткое профессиональное название (до 100 символов)",
        "description": "подробное описание с техническими деталями",
        "queue": "ключ очереди из списка доступных",
        "priority": "приоритет из списка доступных",
        "assignee": "имя исполнителя или null",
        "deadline": "срок в YYYY-MM-DD или null",
        "tags": ["список тегов через запятую или null"],
        "type": "тип задачи (bug, task, feature, epic) или null"
    }},
    "missing_data": ["список недостающих данных"],
    "confidence": 0.0-1.0,
    "reasoning": "краткое объяснение решения",
    "text_refactoring": {{
        "original": "исходный текст",
        "improved": "улучшенная версия текста",
        "changes": ["список внесенных улучшений"]
    }}
}}

ПРАВИЛА АНАЛИЗА И РЕФАКТОРИНГА:

1. НАМЕРЕНИЕ СОЗДАТЬ ЗАДАЧУ:
- Ключевые слова: "создай", "создать", "добавь", "новая задача", "баг", "ошибка", "исправить"
- Технические термины: "функция", "модуль", "интеграция", "тестирование"

2. ДОСТАТОЧНОСТЬ ДАННЫХ:
- Есть описание что нужно сделать
- Есть технический контекст
- Есть указание на проблему или задачу

3. РЕФАКТОРИНГ ТЕКСТА:
- Убирай разговорные фразы ("нужно", "хочу", "пожалуйста")
- Добавляй технические детали
- Структурируй описание
- Используй профессиональную терминологию
- Добавляй контекст и предысторию

4. ОПРЕДЕЛЕНИЕ ОЧЕРЕДИ:
- DEV/TEST/BUG - для разработки и тестирования
- DOC/WIKI - для документации
- DESIGN/UI - для дизайна
- По умолчанию - первая доступная

5. ОПРЕДЕЛЕНИЕ ПРИОРИТЕТА:
- Критический: блокеры, критические баги, срочные задачи
- Высокий: важные баги, новые функции
- Средний: обычные задачи, улучшения
- Низкий: документация, косметические изменения

6. ТИПЫ ЗАДАЧ:
- bug: ошибки, баги, проблемы
- task: обычные задачи, доработки
- feature: новые функции, возможности
- epic: крупные задачи, эпики

ПРИМЕРЫ РЕФАКТОРИНГА:
"создай задачу исправить баг в авторизации" -> 
"Исправить ошибку аутентификации в модуле авторизации"

"нужно добавить новую функцию поиска" ->
"Реализовать расширенную функцию поиска с фильтрацией и сортировкой"

"хочу документацию для API" ->
"Создать техническую документацию для REST API с примерами запросов"

Отвечай только JSON без дополнительного текста.
"""

        try:
            logger.info(f"Анализируем намерение создания задачи: {user_text[:50]}...")
            response = await self._call_llm(prompt)
            
            # Извлекаем JSON из ответа
            json_start = response.find('{')
            json_end = response.rfind('}') + 1
            if json_start != -1 and json_end != 0:
                json_str = response[json_start:json_end]
                try:
                    parsed = json.loads(json_str)
                    logger.info(f"Результат анализа намерения: {parsed}")
                    return parsed
                except json.JSONDecodeError:
                    # Пробуем исправить JSON
                    fixed_json = self._fix_json_response(json_str)
                    if fixed_json:
                        try:
                            parsed = json.loads(fixed_json)
                            logger.info(f"Исправленный JSON анализа: {parsed}")
                            return parsed
                        except json.JSONDecodeError:
                            pass
            
            # Fallback анализ
            logger.warning("Не удалось распарсить JSON анализа, используем fallback")
            return self._fallback_intent_analysis(user_text, available_queues, available_priorities)
            
        except Exception as e:
            logger.error(f"Ошибка при анализе намерения создания задачи: {e}")
            return self._fallback_intent_analysis(user_text, available_queues, available_priorities)

    def _fallback_intent_analysis(self, user_text: str, available_queues: List[str], available_priorities: Optional[List[str]]) -> Dict[str, Any]:
        """Fallback анализ намерения создания задачи"""
        text_lower = user_text.lower()
        
        # Проверяем намерение создать задачу
        create_keywords = ['создай', 'создать', 'добавь', 'добавить', 'новая задача', 'новый тикет']
        wants_to_create = any(keyword in text_lower for keyword in create_keywords)
        
        if not wants_to_create:
            return {
                "wants_to_create_task": False,
                "has_sufficient_data": False,
                "extracted_data": {
                    "summary": None,
                    "description": None,
                    "queue": None,
                    "priority": None,
                    "assignee": None,
                    "deadline": None,
                    "tags": None,
                    "type": None
                },
                "missing_data": [],
                "confidence": 0.8,
                "reasoning": "Текст не содержит намерения создать задачу"
            }
        
        # Проверяем достаточность данных
        has_description = len(user_text.split()) > 3 and any(word in text_lower for word in ['баг', 'ошибка', 'исправить', 'добавить', 'сделать', 'настроить'])
        
        # Определяем приоритет по умолчанию
        default_priority = "Средний"
        if available_priorities:
            if "Средний" in available_priorities:
                default_priority = "Средний"
            else:
                default_priority = available_priorities[0]
        
        extracted_data = {
            "summary": user_text[:100] if has_description else None,
            "description": user_text if has_description else None,
            "queue": available_queues[0] if available_queues else None,
            "priority": default_priority,
            "assignee": None,
            "deadline": None,
            "tags": None,
            "type": "task"
        }
        
        missing_data = []
        if not has_description:
            missing_data.append("описание задачи")
        
        return {
            "wants_to_create_task": True,
            "has_sufficient_data": has_description,
            "extracted_data": extracted_data,
            "missing_data": missing_data,
            "confidence": 0.7,
            "reasoning": f"Намерение создать задачу обнаружено, {'достаточно' if has_description else 'недостаточно'} данных"
        } 

    async def refactor_task_text(self, text: str) -> Dict[str, Any]:
        """Рефакторить текст задачи для улучшения качества"""
        prompt = f"""
Ты - эксперт по техническому письму и созданию задач в системах управления проектами.

Исходный текст: {text}

Отрефакторь текст, сделав его более профессиональным и информативным.

ОТВЕТЬ В ФОРМАТЕ JSON:
{{
    "original": "исходный текст",
    "improved": "улучшенная версия",
    "summary": "краткое название (до 100 символов)",
    "description": "подробное описание",
    "changes": [
        "убрал разговорные фразы",
        "добавил технические детали",
        "структурировал описание"
    ],
    "suggested_type": "bug/task/feature/epic",
    "suggested_priority": "Низкий/Средний/Высокий/Критический"
}}

ПРАВИЛА РЕФАКТОРИНГА:

1. УБИРАЙ:
- Разговорные фразы: "нужно", "хочу", "пожалуйста", "сделай"
- Неопределенные слова: "что-то", "как-то", "где-то"
- Личные местоимения: "я", "мы", "он"

2. ДОБАВЛЯЙ:
- Технические детали и контекст
- Предысторию проблемы
- Ожидаемый результат
- Критерии выполнения

3. СТРУКТУРИРУЙ:
- Проблема/задача
- Контекст
- Требования
- Ожидаемый результат

4. ИСПОЛЬЗУЙ:
- Профессиональную терминологию
- Конкретные технические термины
- Четкие формулировки

ПРИМЕРЫ:
"баг в авторизации" -> 
"Ошибка аутентификации пользователей в модуле авторизации при использовании OAuth2"

"добавить поиск" ->
"Реализовать полнотекстовый поиск с поддержкой фильтров и сортировки"

"документация API" ->
"Создать техническую документацию REST API с примерами запросов и ответов"

Отвечай только JSON без дополнительного текста.
"""

        try:
            logger.info(f"Рефакторим текст задачи: {text[:50]}...")
            response = await self._call_llm(prompt)
            
            # Извлекаем JSON из ответа
            json_start = response.find('{')
            json_end = response.rfind('}') + 1
            if json_start != -1 and json_end != 0:
                json_str = response[json_start:json_end]
                try:
                    parsed = json.loads(json_str)
                    logger.info(f"Результат рефакторинга: {parsed}")
                    return parsed
                except json.JSONDecodeError:
                    # Пробуем исправить JSON
                    fixed_json = self._fix_json_response(json_str)
                    if fixed_json:
                        try:
                            parsed = json.loads(fixed_json)
                            logger.info(f"Исправленный JSON рефакторинга: {parsed}")
                            return parsed
                        except json.JSONDecodeError:
                            pass
            
            # Fallback
            logger.warning("Не удалось распарсить JSON рефакторинга, используем fallback")
            return {
                "original": text,
                "improved": text,
                "summary": text[:100],
                "description": text,
                "changes": ["не удалось отрефакторить"],
                "suggested_type": "task",
                "suggested_priority": "Средний"
            }
            
        except Exception as e:
            logger.error(f"Ошибка при рефакторинге текста: {e}")
            return {
                "original": text,
                "improved": text,
                "summary": text[:100],
                "description": text,
                "changes": ["ошибка рефакторинга"],
                "suggested_type": "task",
                "suggested_priority": "Средний"
            } 