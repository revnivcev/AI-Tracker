#!/usr/bin/env python3
"""
Скрипт для заполнения Yandex Tracker моковыми данными
Создает задачи на 28-30 июля 2025 года с комментариями, статусами и исполнителем
"""

import os
import sys
import random
import time
from datetime import datetime, timedelta
from typing import List, Dict, Any

# Добавляем путь к проекту
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.config import settings
from app.services.tracker_service import TrackerService

# Настройки для моковых данных
MOCK_DATA = {
    "queues": ["OCHERED", "NOVAYATESTOVAYA"],
    "priorities": ["trivial", "minor", "normal", "critical", "blocker"],
    "statuses": ["open", "inProgress", "resolved", "closed"],
    "assignee": "Андрей Ревнивцев",
    "dates": ["2025-07-28", "2025-07-29", "2025-07-30"]
}

# Список моковых задач
TASKS = [
    # 28 июля 2025
    {
        "summary": "Рефакторинг модуля авторизации",
        "description": "Необходимо переписать модуль авторизации для улучшения производительности и безопасности. Добавить поддержку OAuth 2.0 и двухфакторной аутентификации.",
        "priority": "critical",
        "status": "inProgress",
        "date": "2025-07-28",
        "queue": "OCHERED",
        "comments": [
            "Начал работу над рефакторингом. Обнаружил несколько уязвимостей в текущей реализации.",
            "Добавил базовую поддержку OAuth 2.0. Нужно протестировать с разными провайдерами.",
            "Завершил основную часть рефакторинга. Осталось добавить тесты."
        ]
    },
    {
        "summary": "Исправление багов в платежной системе",
        "description": "Критические баги в обработке платежей. Пользователи не могут завершить покупки. Срочно требуется исправление.",
        "priority": "blocker",
        "status": "open",
        "date": "2025-07-28",
        "queue": "OCHERED",
        "comments": [
            "Проанализировал логи ошибок. Проблема в валидации платежных данных.",
            "Написал исправления для основных сценариев. Требуется тестирование."
        ]
    },
    {
        "summary": "Добавление новых полей в профиль пользователя",
        "description": "Расширить профиль пользователя: добавить поле для аватара, дату рождения, предпочтения уведомлений.",
        "priority": "normal",
        "status": "open",
        "date": "2025-07-28",
        "queue": "NOVAYATESTOVAYA",
        "comments": [
            "Создал миграцию базы данных для новых полей.",
            "Добавил валидацию для новых полей. Нужно обновить API."
        ]
    },
    
    # 29 июля 2025
    {
        "summary": "Оптимизация запросов к базе данных",
        "description": "Медленная работа приложения из-за неоптимальных SQL запросов. Необходимо добавить индексы и переписать медленные запросы.",
        "priority": "critical",
        "status": "inProgress",
        "date": "2025-07-29",
        "queue": "OCHERED",
        "comments": [
            "Проанализировал медленные запросы. Нашел 5 проблемных мест.",
            "Добавил индексы для основных таблиц. Время ответа улучшилось на 40%.",
            "Переписал запросы для отчета по продажам. Осталось протестировать."
        ]
    },
    {
        "summary": "Интеграция с внешним API",
        "description": "Интеграция с сервисом доставки для расчета стоимости и времени доставки заказов.",
        "priority": "normal",
        "status": "resolved",
        "date": "2025-07-29",
        "queue": "NOVAYATESTOVAYA",
        "comments": [
            "Изучил документацию API доставки. Подготовил план интеграции.",
            "Создал клиент для работы с API. Добавил обработку ошибок.",
            "Интеграция завершена. API работает корректно, все тесты пройдены."
        ]
    },
    {
        "summary": "Обновление дизайна главной страницы",
        "description": "Модернизация дизайна главной страницы сайта. Добавить современные элементы UI, улучшить мобильную версию.",
        "priority": "minor",
        "status": "open",
        "date": "2025-07-29",
        "queue": "NOVAYATESTOVAYA",
        "comments": [
            "Подготовил макеты нового дизайна. Получил одобрение от дизайнера.",
            "Начал верстку основных компонентов."
        ]
    },
    {
        "summary": "Настройка мониторинга системы",
        "description": "Установка и настройка системы мониторинга для отслеживания производительности и доступности приложения.",
        "priority": "normal",
        "status": "inProgress",
        "date": "2025-07-29",
        "queue": "OCHERED",
        "comments": [
            "Установил Prometheus и Grafana на серверах.",
            "Настроил базовые метрики: CPU, память, диск. Добавил алерты.",
            "Интегрировал мониторинг с основным приложением. Нужно добавить кастомные метрики."
        ]
    },
    
    # 30 июля 2025
    {
        "summary": "Миграция на новую версию фреймворка",
        "description": "Обновление основного фреймворка с версии 2.1 до 3.0. Проверить совместимость всех модулей.",
        "priority": "critical",
        "status": "open",
        "date": "2025-07-30",
        "queue": "OCHERED",
        "comments": [
            "Изучил changelog новой версии. Выявил breaking changes.",
            "Создал план миграции с учетом всех изменений."
        ]
    },
    {
        "summary": "Добавление системы уведомлений",
        "description": "Реализация системы push-уведомлений для мобильного приложения. Поддержка email и SMS уведомлений.",
        "priority": "normal",
        "status": "inProgress",
        "date": "2025-07-30",
        "queue": "NOVAYATESTOVAYA",
        "comments": [
            "Создал архитектуру системы уведомлений. Выбрал Firebase для push.",
            "Интегрировал Firebase SDK. Настроил отправку email через SMTP.",
            "Добавил шаблоны уведомлений. Осталось протестировать на реальных устройствах."
        ]
    },
    {
        "summary": "Исправление проблем с кэшированием",
        "description": "Проблемы с Redis кэшем: медленная работа, потеря данных. Необходимо оптимизировать и добавить резервное копирование.",
        "priority": "critical",
        "status": "resolved",
        "date": "2025-07-30",
        "queue": "OCHERED",
        "comments": [
            "Проанализировал проблемы с Redis. Нашел утечки памяти.",
            "Оптимизировал настройки Redis. Добавил мониторинг памяти.",
            "Настроил репликацию и резервное копирование. Проблемы решены."
        ]
    },
    {
        "summary": "Создание API документации",
        "description": "Генерация автоматической документации для REST API с помощью Swagger/OpenAPI. Добавить примеры запросов и ответов.",
        "priority": "minor",
        "status": "closed",
        "date": "2025-07-30",
        "queue": "NOVAYATESTOVAYA",
        "comments": [
            "Настроил Swagger UI для API. Добавил базовые аннотации.",
            "Дополнил документацию примерами для всех эндпоинтов.",
            "Документация готова и доступна по адресу /api/docs"
        ]
    },
    {
        "summary": "Оптимизация загрузки изображений",
        "description": "Медленная загрузка изображений на сайте. Добавить сжатие, lazy loading и CDN для улучшения производительности.",
        "priority": "normal",
        "status": "inProgress",
        "date": "2025-07-30",
        "queue": "NOVAYATESTOVAYA",
        "comments": [
            "Настроил автоматическое сжатие изображений при загрузке.",
            "Добавил lazy loading для галерей. Интегрировал CDN CloudFlare.",
            "Производительность улучшилась на 60%. Осталось протестировать на мобильных устройствах."
        ]
    }
]

class MockDataCreator:
    def __init__(self):
        self.tracker_service = TrackerService(
            token=settings.YANDEX_TRACKER_TOKEN,
            org_id=settings.YANDEX_ORG_ID,
            cloud_org_id=settings.YANDEX_CLOUD_ORG_ID
        )
        
    def create_task(self, task_data: Dict[str, Any]) -> bool:
        """Создать задачу в Yandex Tracker"""
        try:
            print(f"Создаю задачу: {task_data['summary']}")
            
            # Создаем задачу (без назначения исполнителя)
            issue = self.tracker_service.client.issues.create(
                summary=task_data['summary'],
                description=task_data['description'],
                queue=task_data['queue'],
                priority=task_data['priority']
            )
            
            if not issue:
                print(f"❌ Не удалось создать задачу: {task_data['summary']}")
                return False
                
            print(f"✅ Задача создана: {issue.key}")
            
            # Добавляем комментарии
            for comment_text in task_data.get('comments', []):
                try:
                    self.tracker_service.client.issues[issue.key].comments.create(
                        text=comment_text
                    )
                    print(f"  📝 Добавлен комментарий: {comment_text[:50]}...")
                    time.sleep(1)  # Небольшая задержка между комментариями
                except Exception as e:
                    print(f"  ⚠️ Ошибка при добавлении комментария: {e}")
            
            # Изменяем статус если нужно
            if task_data['status'] != 'open':
                try:
                    # Получаем доступные переходы статусов
                    transitions = self.tracker_service.client.issues[issue.key].transitions.get()
                    
                    # Находим нужный переход
                    target_status = task_data['status']
                    for transition in transitions:
                        if target_status in transition.id.lower() or target_status in transition.display.lower():
                            self.tracker_service.client.issues[issue.key].transitions[transition.id].post()
                            print(f"  🔄 Статус изменен на: {target_status}")
                            break
                            
                except Exception as e:
                    print(f"  ⚠️ Ошибка при изменении статуса: {e}")
            
            return True
            
        except Exception as e:
            print(f"❌ Ошибка при создании задачи {task_data['summary']}: {e}")
            return False
    
    def run(self):
        """Запустить создание моковых данных"""
        print("🚀 Запуск создания моковых данных в Yandex Tracker")
        print("=" * 60)
        
        # Проверяем доступность API
        try:
            queues = self.tracker_service.get_queues()
            print(f"✅ Подключение к Yandex Tracker успешно. Доступно очередей: {len(queues)}")
        except Exception as e:
            print(f"❌ Ошибка подключения к Yandex Tracker: {e}")
            return
        
        # Создаем задачи
        created_count = 0
        total_count = len(TASKS)
        
        for i, task_data in enumerate(TASKS, 1):
            print(f"\n📋 [{i}/{total_count}] Создание задачи...")
            
            if self.create_task(task_data):
                created_count += 1
            
            # Небольшая задержка между созданием задач
            time.sleep(2)
        
        print("\n" + "=" * 60)
        print(f"🎉 Создание моковых данных завершено!")
        print(f"✅ Успешно создано: {created_count}/{total_count} задач")
        print(f"📅 Период: 28-30 июля 2025")
        print(f"👤 Исполнитель: {MOCK_DATA['assignee']}")
        print(f"📊 Очереди: {', '.join(MOCK_DATA['queues'])}")

def main():
    """Главная функция"""
    if not settings.YANDEX_TRACKER_TOKEN or settings.YANDEX_TRACKER_TOKEN == "your_yandex_tracker_token_here":
        print("❌ Ошибка: Не настроен YANDEX_TRACKER_TOKEN в .env файле")
        return
    
    creator = MockDataCreator()
    creator.run()

if __name__ == "__main__":
    main() 