import logging
from typing import List, Dict, Optional, Any
from yandex_tracker_client import TrackerClient
from app.config import settings
from datetime import datetime

logger = logging.getLogger(__name__)


class TrackerService:
    def __init__(self, token: str, org_id: Optional[str] = None, cloud_org_id: Optional[str] = None):
        # Определяем тип организации по результатам тестирования
        # У пользователя Cloud организация, поэтому используем cloud_org_id
        client_kwargs = {"token": token}
        
        # Для Cloud организаций используем cloud_org_id
        if getattr(settings, "YANDEX_CLOUD_ORG_ID", None):
            client_kwargs["cloud_org_id"] = settings.YANDEX_CLOUD_ORG_ID
        elif cloud_org_id:
            client_kwargs["cloud_org_id"] = cloud_org_id
        elif org_id:
            # Если cloud_org_id не задан, используем org_id как cloud_org_id
            client_kwargs["cloud_org_id"] = org_id
            
        self.client = TrackerClient(**client_kwargs)
        self.org_id = org_id
        self.cloud_org_id = getattr(settings, "YANDEX_CLOUD_ORG_ID", cloud_org_id or org_id)

    def get_queues(self) -> List[Dict[str, Any]]:
        """Получить список очередей"""
        try:
            logger.info(f"Запрашиваем очереди с org_id={self.org_id}, cloud_org_id={self.cloud_org_id}")
            queues = self.client.queues.get_all()
            logger.info(f"Получено {len(queues)} очередей из Yandex Tracker")
            
            result = []
            for queue in queues:
                try:
                    queue_data = {
                        'id': queue.id,
                        'key': queue.key,
                        'name': queue.name,
                        'description': getattr(queue, 'description', '')
                    }
                    result.append(queue_data)
                    logger.info(f"Очередь: {queue.key} - {queue.name}")
                except Exception as e:
                    logger.error(f"Ошибка при обработке очереди: {e}")
                    continue
                    
            return result
        except Exception as e:
            logger.error(f"Ошибка при получении очередей: {e}")
            return []

    def get_queue_issues(self, queue_key: str, filter_query: Optional[str] = None) -> List[Dict[str, Any]]:
        """Получить задачи из очереди"""
        try:
            # Формируем фильтр для получения задач из конкретной очереди
            # Используем правильный синтаксис запроса Yandex Tracker
            query = f'Queue: "{queue_key}"'
            if filter_query:
                query += f' AND {filter_query}'

            logger.info(f"Выполняем запрос к Yandex Tracker: {query}")
            issues = self.client.issues.find(query=query, per_page=100)
            
            result = []
            for issue in issues:
                try:
                    # Безопасное получение атрибутов с fallback значениями
                    issue_data = {
                        'id': getattr(issue, 'id', 'unknown'),
                        'key': getattr(issue, 'key', 'unknown'),
                        'summary': getattr(issue, 'summary', 'Без названия'),
                        'status': self._safe_get_status(issue),
                        'assignee': self._safe_get_assignee(issue),
                        'priority': self._safe_get_priority(issue),
                        'created': getattr(issue, 'created', None),
                        'updated': getattr(issue, 'updated', None),
                        'description': getattr(issue, 'description', ''),
                        'queue': queue_key
                    }
                    result.append(issue_data)
                    logger.info(f"Обработана задача: {issue_data['key']} - {issue_data['summary']}")
                except Exception as e:
                    logger.error(f"Ошибка при обработке задачи {getattr(issue, 'key', 'unknown')}: {e}")
                    continue
            
            logger.info(f"Получено {len(result)} задач из очереди {queue_key}")
            return result
            
        except Exception as e:
            logger.error(f"Ошибка при получении задач из очереди {queue_key}: {e}")
            return []

    def _safe_get_status(self, issue) -> str:
        """Безопасное получение статуса задачи"""
        try:
            status_obj = getattr(issue, 'status', None)
            if status_obj and hasattr(status_obj, 'get'):
                return status_obj.get('display', 'Unknown')
            elif status_obj and hasattr(status_obj, 'display'):
                return status_obj.display
            else:
                return 'Unknown'
        except Exception as e:
            logger.error(f"Ошибка при получении статуса: {e}")
            return 'Unknown'

    def _safe_get_assignee(self, issue) -> str:
        """Безопасное получение исполнителя задачи"""
        try:
            assignee_obj = getattr(issue, 'assignee', None)
            if assignee_obj and hasattr(assignee_obj, 'get'):
                return assignee_obj.get('display', 'Unassigned')
            elif assignee_obj and hasattr(assignee_obj, 'display'):
                return assignee_obj.display
            else:
                return 'Unassigned'
        except Exception as e:
            logger.error(f"Ошибка при получении исполнителя: {e}")
            return 'Unassigned'

    def _safe_get_priority(self, issue) -> str:
        """Безопасное получение приоритета задачи"""
        try:
            priority_obj = getattr(issue, 'priority', None)
            if priority_obj and hasattr(priority_obj, 'get'):
                return priority_obj.get('display', 'Medium')
            elif priority_obj and hasattr(priority_obj, 'display'):
                return priority_obj.display
            else:
                return 'Medium'
        except Exception as e:
            logger.error(f"Ошибка при получении приоритета: {e}")
            return 'Medium'

    def create_issue(self, queue_key: str, summary: str, description: str = None, assignee: str = None, priority: str = None) -> Optional[Dict[str, Any]]:
        """Создать задачу в очереди"""
        try:
            logger.info(f"Создаем задачу в очереди {queue_key}: {summary}")
            
            # Подготавливаем данные для создания задачи
            issue_data = {
                'summary': summary,
                'description': description or summary,
                'queue': queue_key
            }
            
            # Добавляем приоритет только если он валидный
            if priority:
                # Маппинг приоритетов
                priority_mapping = {
                    'Низкий': 'minor',
                    'Средний': 'normal', 
                    'Высокий': 'critical',
                    'Критический': 'critical',
                    'Блокер': 'blocker',
                    'Незначительный': 'trivial'
                }
                
                mapped_priority = priority_mapping.get(priority, priority)
                if mapped_priority in ['trivial', 'minor', 'normal', 'critical', 'blocker']:
                    issue_data['priority'] = mapped_priority
                    logger.info(f"Устанавливаем приоритет: {mapped_priority}")
            
            # Добавляем исполнителя только если он валидный
            if assignee and assignee != 'я' and assignee != 'me':
                # Здесь можно добавить валидацию пользователей
                # Пока просто логируем
                logger.info(f"Попытка назначить исполнителя: {assignee}")
                # issue_data['assignee'] = assignee  # Раскомментировать после валидации
            
            logger.info(f"Данные для создания задачи: {issue_data}")
            
            # Создаем задачу
            issue = self.client.issues.create(**issue_data)
            
            if issue:
                logger.info(f"Задача создана успешно: {issue.key}")
                return {
                    'key': issue.key,
                    'summary': issue.summary,
                    'queue': queue_key,
                    'status': issue.status.display,
                    'url': f"https://tracker.yandex.ru/{issue.key}"
                }
            else:
                logger.error("Не удалось создать задачу")
                return None
                
        except Exception as e:
            logger.error(f"Ошибка при создании задачи в очереди {queue_key}: {e}")
            return None

    def get_recent_changes(self, queue_key: str, since_date: str) -> List[Dict[str, Any]]:
        """Получить недавние изменения в задачах очереди"""
        try:
            # Фильтр для получения задач, измененных после указанной даты
            # Используем правильный синтаксис запроса Yandex Tracker
            # Yandex Tracker принимает формат YYYY-MM-DD
            try:
                # Парсим дату и конвертируем в формат YYYY-MM-DD
                parsed_date = datetime.fromisoformat(since_date.replace('Z', '+00:00'))
                date_str = parsed_date.strftime('%Y-%m-%d')
            except:
                # Если не удалось распарсить, используем как есть
                date_str = since_date.split('T')[0] if 'T' in since_date else since_date
            
            filter_query = f'Updated: > "{date_str}"'
            logger.info(f"Поиск изменений в очереди {queue_key} с {date_str}")
            return self.get_queue_issues(queue_key, filter_query)
        except Exception as e:
            logger.error(f"Ошибка при получении недавних изменений для очереди {queue_key}: {e}")
            return []

    def get_priorities(self) -> List[Dict[str, Any]]:
        """Получить список доступных приоритетов"""
        try:
            logger.info("Запрашиваем приоритеты из Yandex Tracker")
            priorities = self.client.priorities.get_all()
            logger.info(f"Получено {len(priorities)} приоритетов из Yandex Tracker")
            
            result = []
            for priority in priorities:
                try:
                    priority_data = {
                        'id': priority.id,
                        'key': priority.key,
                        'name': priority.name,
                        'display': getattr(priority, 'display', priority.name)
                    }
                    result.append(priority_data)
                    logger.info(f"Приоритет: {priority.key} - {priority.name}")
                except Exception as e:
                    logger.error(f"Ошибка при обработке приоритета: {e}")
                    continue
                    
            return result
        except Exception as e:
            logger.error(f"Ошибка при получении приоритетов: {e}")
            return [] 