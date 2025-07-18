import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from app.services.tracker_service import TrackerService
from app.services.llm_service import LLMService
from app.models.database import get_db
from app.models.digest_log import DigestLog
import re

logger = logging.getLogger(__name__)


class DigestService:
    def __init__(self, tracker_service: TrackerService, llm_service: LLMService):
        self.tracker_service = tracker_service
        self.llm_service = llm_service

    async def generate_digest(self, user_id: int, queue_key: str, since_hours: int = 24, status_callback=None) -> Optional[str]:
        """Генерировать дайджест для очереди с отслеживанием изменений"""
        try:
            logger.info(f"Генерируем дайджест для очереди {queue_key}")
            
            # Получаем время последнего дайджеста
            last_digest_time = self._get_last_digest_time(user_id, queue_key)
            
            if status_callback:
                await status_callback("📡 Получаю данные из Yandex Tracker...")
            
            # Получаем ВСЕ задачи из очереди
            all_issues = self.tracker_service.get_queue_issues(queue_key)
            logger.info(f"Получено {len(all_issues)} задач из очереди {queue_key}")
            
            if not all_issues:
                logger.info(f"Нет задач в очереди {queue_key}")
                return self._format_empty_digest(queue_key, since_hours)

            # Определяем период для анализа изменений
            if last_digest_time:
                # Если есть предыдущий дайджест, анализируем изменения с того момента
                cutoff_time = last_digest_time
                time_description = f"с {last_digest_time.strftime('%d.%m.%Y %H:%M')}"
                logger.info(f"Анализируем изменения {time_description}")
            else:
                # Если нет предыдущего дайджеста, используем фиксированный период
                cutoff_time = datetime.now() - timedelta(hours=since_hours)
                time_description = f"за последние {since_hours} часов"
                logger.info(f"Первый дайджест, анализируем {time_description}")

            # Фильтруем задачи по дате обновления
            recent_issues = []
            for issue in all_issues:
                updated_str = issue.get('updated')
                if updated_str:
                    try:
                        # Парсим дату обновления
                        if 'T' in updated_str:
                            updated_time = datetime.fromisoformat(updated_str.replace('Z', '+00:00'))
                        else:
                            updated_time = datetime.fromisoformat(updated_str)
                        
                        # Проверяем, была ли задача обновлена в указанный период
                        if updated_time >= cutoff_time:
                            recent_issues.append(issue)
                            logger.info(f"Задача {issue.get('key')} обновлена {updated_time} - включаем в дайджест")
                        else:
                            logger.info(f"Задача {issue.get('key')} обновлена {updated_time} - слишком старая")
                    except Exception as e:
                        logger.error(f"Ошибка при парсинге даты {updated_str}: {e}")
                        # Если не удалось распарсить дату, включаем задачу
                        recent_issues.append(issue)
                else:
                    # Если нет даты обновления, включаем задачу
                    recent_issues.append(issue)
                    logger.info(f"Задача {issue.get('key')} без даты обновления - включаем в дайджест")

            logger.info(f"Отфильтровано {len(recent_issues)} задач {time_description}")
            
            if not recent_issues:
                logger.info(f"Нет изменений в очереди {queue_key} {time_description}")
                return self._format_no_changes_digest(queue_key, time_description)

            # Группируем задачи по статусу
            if status_callback:
                await status_callback("📊 Группирую задачи по статусам...")
                
            status_groups = await self._group_issues_by_status(recent_issues)

            # Генерируем резюме изменений
            if status_callback:
                await status_callback("🤖 Анализирую изменения...")
                
            summary = await self._generate_changes_summary(queue_key, status_groups, recent_issues, last_digest_time)

            # Формируем дайджест
            if status_callback:
                await status_callback("📝 Формирую дайджест...")
                
            digest = self._format_digest(queue_key, status_groups, summary, time_description)

            # Логируем дайджест
            self._log_digest(user_id, queue_key, digest, len(recent_issues))

            return digest

        except Exception as e:
            logger.error(f"Ошибка при генерации дайджеста для очереди {queue_key}: {e}")
            queue_url = f"https://tracker.yandex.ru/queues/{queue_key}"
            return f"❌ Ошибка при генерации дайджеста для очереди <a href=\"{queue_url}\">{queue_key}</a>"

    def _get_last_digest_time(self, user_id: int, queue_key: str) -> Optional[datetime]:
        """Получить время последнего дайджеста для пользователя и очереди"""
        try:
            db = next(get_db())
            last_digest = db.query(DigestLog).filter(
                DigestLog.user_id == user_id,
                DigestLog.queue_key == queue_key
            ).order_by(DigestLog.created_at.desc()).first()
            
            if last_digest:
                created_at = last_digest.created_at
                logger.info(f"Последний дайджест для {queue_key}: {created_at}")
                return created_at.replace(tzinfo=None)
            else:
                logger.info(f"Нет предыдущих дайджестов для {queue_key}")
                return None
                
        except Exception as e:
            logger.error(f"Ошибка при получении времени последнего дайджеста: {e}")
            return None

    def _format_empty_digest(self, queue_key: str, since_hours: int) -> str:
        """Форматировать дайджест для пустой очереди"""
        queue_url = f"https://tracker.yandex.ru/queues/{queue_key}"
        current_time = datetime.now().strftime('%d.%m.%Y %H:%M UTC')
        
        return f"""📊 <b>Дайджест очереди <a href="{queue_url}">{queue_key}</a></b>
📅 За последние {since_hours} часов
🕐 Сформирован: {current_time}

📝 Нет задач в очереди."""

    def _format_no_changes_digest(self, queue_key: str, time_description: str) -> str:
        """Форматировать дайджест при отсутствии изменений"""
        queue_url = f"https://tracker.yandex.ru/queues/{queue_key}"
        current_time = datetime.now().strftime('%d.%m.%Y %H:%M UTC')
        
        return f"""📊 <b>Дайджест очереди <a href="{queue_url}">{queue_key}</a></b>
📅 {time_description}
🕐 Сформирован: {current_time}

📝 Нет изменений в задачах за этот период."""

    async def _generate_changes_summary(self, queue_key: str, status_groups: Dict[str, List[Dict]], issues: List[Dict], last_digest_time: Optional[datetime]) -> str:
        """Генерировать резюме изменений относительно последнего дайджеста"""
        try:
            # Подготавливаем данные для LLM
            summary_data = {
                "queue_key": queue_key,
                "total_issues": len(issues),
                "status_groups": status_groups,
                "issues": issues,
                "last_digest_time": last_digest_time,
                "current_time": datetime.now()
            }
            
            summary = await self.llm_service.create_changes_summary(summary_data)
            return summary if summary else "Обнаружены изменения в задачах."
            
        except Exception as e:
            logger.error(f"Ошибка при генерации резюме изменений для очереди {queue_key}: {e}")
            # Возвращаем fallback с информацией о пользователях
            participants = self._extract_participants(status_groups)
            fallback = f"Обнаружены изменения в {len(issues)} задачах. "
            if participants:
                fallback += f"Задействованные участники: {', '.join(participants)}. "
            
            # Добавляем краткую сводку по статусам
            for status, status_issues in status_groups.items():
                if status_issues:
                    fallback += f"{status}: {len(status_issues)} задач. "
            
            return fallback

    async def _group_issues_by_status(self, issues: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
        """Группировать задачи по статусу через LLM"""
        status_groups = {
            'To Do': [],
            'In Progress': [],
            'Blocked': [],
            'Done': []
        }

        logger.info(f"Группируем {len(issues)} задач по статусам через LLM")
        
        for issue in issues:
            original_status = issue.get('status', 'Unknown')
            
            # Используем LLM для классификации статуса
            normalized_status = await self.llm_service.classify_status(original_status)
            
            logger.info(f"Задача {issue.get('key', 'unknown')}: '{original_status}' -> '{normalized_status}' (LLM)")
            
            if normalized_status in status_groups:
                status_groups[normalized_status].append(issue)
            else:
                logger.warning(f"LLM вернул неизвестный статус '{normalized_status}', добавляем в 'To Do'")
                status_groups['To Do'].append(issue)  # По умолчанию

        # Логируем итоговую группировку
        for status, status_issues in status_groups.items():
            logger.info(f"Статус '{status}': {len(status_issues)} задач")

        return status_groups

    def _normalize_status(self, status: str) -> str:
        """Нормализовать статус задачи"""
        status_lower = status.lower()
        logger.info(f"Нормализуем статус: '{status}' -> '{status_lower}'")
        
        # Выполненные задачи (исправлено - было неправильное условие)
        if any(word in status_lower for word in ['done', 'готово', 'complete', 'завершено', 'решено', 'resolved', 'closed', 'закрыто', 'выполнено']):
            logger.info(f"Статус '{status}' определен как 'Done'")
            return 'Done'
        # В работе
        elif any(word in status_lower for word in ['progress', 'в работе', 'in progress', 'работа', 'выполняется', 'в процессе']):
            logger.info(f"Статус '{status}' определен как 'In Progress'")
            return 'In Progress'
        # Заблокированные
        elif any(word in status_lower for word in ['blocked', 'блок', 'block', 'блокировано', 'заблокировано', 'требуется информация', 'information required', 'need info', 'info needed']):
            logger.info(f"Статус '{status}' определен как 'Blocked'")
            return 'Blocked'
        # К выполнению
        elif any(word in status_lower for word in ['todo', 'to do', 'новая', 'new', 'к выполнению', 'открыта', 'open', 'открыт']):
            logger.info(f"Статус '{status}' определен как 'To Do'")
            return 'To Do'
        else:
            logger.warning(f"Неизвестный статус '{status}', используем 'To Do' по умолчанию")
            return 'To Do'

    def _extract_participants(self, status_groups: Dict[str, List[Dict]]) -> List[str]:
        """Извлечь список участников из задач"""
        participants = set()
        for issues in status_groups.values():
            for issue in issues:
                assignee = issue.get('assignee', '')
                if assignee and assignee.strip() and assignee != 'Unassigned':
                    participants.add(assignee.strip())
        return list(participants)

    def _format_digest(self, queue_key: str, status_groups: Dict[str, List[Dict]], summary: str, time_description: str) -> str:
        """Форматировать дайджест с гиперссылками в HTML формате для Telegram"""
        logger.info(f"Форматируем дайджест для очереди {queue_key}")
        logger.info(f"Статусы в дайджесте: {list(status_groups.keys())}")
        
        # Формируем URL для очереди
        queue_url = f"https://tracker.yandex.ru/queues/{queue_key}"
        current_time = datetime.now().strftime('%d.%m.%Y %H:%M UTC')
        
        digest = f"📊 <b>Дайджест очереди <a href=\"{queue_url}\">{queue_key}</a></b>\n"
        digest += f"📅 {time_description}\n"
        digest += f"🕐 Сформирован: {current_time}\n\n"

        # Добавляем резюме с гиперссылками на очереди
        if summary and summary.strip():
            # Убираем возможные дублирующиеся заголовки из LLM
            clean_summary = summary.strip()
            if clean_summary.startswith("📝 Резюме:"):
                clean_summary = clean_summary.replace("📝 Резюме:", "").strip()
            if clean_summary.startswith("Резюме:"):
                clean_summary = clean_summary.replace("Резюме:", "").strip()
            
            # Заменяем упоминания очереди на гиперссылки в HTML формате
            # Паттерн для поиска упоминаний очереди (с учетом регистра)
            queue_pattern = re.compile(r'\b' + re.escape(queue_key) + r'\b', re.IGNORECASE)
            clean_summary = queue_pattern.sub(f'<a href="{queue_url}">{queue_key}</a>', clean_summary)
                
            digest += f"📝 <b>Резюме:</b> {clean_summary}\n\n"

        # Добавляем участников (если есть)
        participants = self._extract_participants(status_groups)
        if participants:
            digest += f"👥 <b>Задействованные участники:</b> {', '.join(participants)}\n\n"

        # Добавляем задачи по статусам
        for status, issues in status_groups.items():
            if issues:
                logger.info(f"Добавляем статус '{status}' с {len(issues)} задачами")
                digest += f"📋 <b>{status} ({len(issues)}):</b>\n"
                for issue in issues:
                    assignee = issue.get('assignee', '')
                    assignee_text = f" (👤 {assignee})" if assignee and assignee != 'Unassigned' else ""
                    
                    # Формируем URL для задачи
                    issue_key = issue.get('key', '')
                    issue_url = f"https://tracker.yandex.ru/{issue_key}"
                    
                    # Используем HTML разметку для ссылок
                    digest += f"• <a href=\"{issue_url}\">{issue_key}</a> – {issue.get('summary', '')}{assignee_text}\n"
                digest += "\n"

        logger.info(f"Дайджест сформирован, длина: {len(digest)} символов")
        return digest

    def _log_digest(self, user_id: int, queue_key: str, digest_text: str, issues_count: int):
        """Логировать дайджест в базу данных"""
        try:
            db = next(get_db())
            log_entry = DigestLog(
                user_id=user_id,
                queue_key=queue_key,
                digest_text=digest_text,
                issues_count=issues_count
            )
            db.add(log_entry)
            db.commit()
        except Exception as e:
            logger.error(f"Ошибка при логировании дайджеста: {e}") 