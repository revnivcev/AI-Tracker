#!/usr/bin/env python3
"""
Демонстрационный скрипт для создания задач в очереди FULLSTACK
Создает реалистичные user stories для кросс-функциональной команды
"""

import requests
import json
import time
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv

# Загружаем переменные окружения
load_dotenv()

class DemoDataCreator:
    def __init__(self):
        self.token = os.getenv('YANDEX_TRACKER_TOKEN')
        self.cloud_org_id = os.getenv('YANDEX_CLOUD_ORG_ID')
        self.base_url = "https://api.tracker.yandex.net/v2"
        self.headers = {
            'Authorization': f'OAuth {self.token}',
            'X-Cloud-Org-Id': self.cloud_org_id,
            'Content-Type': 'application/json'
        }
        self.queue_key = "FULLSTACK"
        
    def create_issue(self, summary, description, priority="normal"):
        """Создает задачу в очереди"""
        try:
            issue_data = {
                "summary": summary,
                "description": description,
                "queue": self.queue_key,
                "priority": priority
            }
                
            response = requests.post(
                f"{self.base_url}/issues",
                headers=self.headers,
                json=issue_data
            )
            
            if response.status_code == 201:
                issue = response.json()
                print(f"✅ Создана задача: {issue['key']} - {summary}")
                return issue
            else:
                print(f"❌ Ошибка создания задачи: {response.status_code} - {response.text}")
                return None
                
        except Exception as e:
            print(f"❌ Ошибка: {e}")
            return None
    
    def add_comment(self, issue_key, comment_text):
        """Добавляет комментарий к задаче"""
        try:
            comment_data = {
                "text": comment_text
            }
            
            response = requests.post(
                f"{self.base_url}/issues/{issue_key}/comments",
                headers=self.headers,
                json=comment_data
            )
            
            if response.status_code == 201:
                print(f"💬 Добавлен комментарий к {issue_key}")
            else:
                print(f"❌ Ошибка добавления комментария: {response.status_code}")
                
        except Exception as e:
            print(f"❌ Ошибка: {e}")
    
    def change_status(self, issue_key, status_key):
        """Изменяет статус задачи"""
        try:
            # Получаем доступные переходы
            response = requests.get(
                f"{self.base_url}/issues/{issue_key}/transitions",
                headers=self.headers
            )
            
            if response.status_code == 200:
                transitions = response.json()
                target_transition = None
                
                for transition in transitions:
                    if transition.get('to', {}).get('key') == status_key:
                        target_transition = transition
                        break
                
                if target_transition:
                    # Выполняем переход
                    transition_data = {
                        "transition": target_transition['id']
                    }
                    
                    response = requests.post(
                        f"{self.base_url}/issues/{issue_key}/transitions",
                        headers=self.headers,
                        json=transition_data
                    )
                    
                    if response.status_code == 200:
                        print(f"🔄 Статус {issue_key} изменен на {status_key}")
                    else:
                        print(f"❌ Ошибка изменения статуса: {response.status_code}")
                else:
                    print(f"⚠️ Переход к статусу {status_key} не найден для {issue_key}")
                    
        except Exception as e:
            print(f"❌ Ошибка: {e}")
    
    def create_demo_tasks(self):
        """Создает демонстрационные задачи"""
        print("🚀 Создание демонстрационных задач для очереди FULLSTACK...")
        print("=" * 60)
        
        # Список демонстрационных задач
        demo_tasks = [
            {
                "summary": "Как пользователь, я хочу видеть индикатор загрузки при отправке формы",
                "description": """**User Story:**
Как пользователь, я хочу видеть индикатор загрузки при отправке формы, чтобы понимать, что мой запрос обрабатывается.

**Acceptance Criteria:**
- [ ] При нажатии кнопки "Отправить" появляется спиннер
- [ ] Кнопка становится неактивной во время загрузки
- [ ] Спиннер исчезает после получения ответа от сервера
- [ ] При ошибке показывается уведомление

**Technical Notes:**
- Использовать React Loading Spinner
- Добавить состояние loading в Redux store
- Обработать все возможные ошибки сети

**Story Points:** 3
**Priority:** High""",
                "priority": "critical",
                "status": "inProgress",
                "comments": [
                    "Начинаю работу над компонентом LoadingSpinner",
                    "Добавил состояние loading в Redux. Следующий шаг - интеграция с формами"
                ]
            },
            {
                "summary": "Как администратор, я хочу экспортировать отчеты в Excel",
                "description": """**User Story:**
Как администратор, я хочу экспортировать отчеты в Excel, чтобы анализировать данные в привычном формате.

**Acceptance Criteria:**
- [ ] Кнопка "Экспорт в Excel" на странице отчетов
- [ ] Поддержка всех типов отчетов (пользователи, активность, ошибки)
- [ ] Файл скачивается с правильным именем и расширением .xlsx
- [ ] Прогресс-бар при генерации больших отчетов

**Technical Notes:**
- Использовать библиотеку xlsx для генерации файлов
- Добавить фильтры по датам в экспорт
- Обработать случаи с большими объемами данных

**Story Points:** 5
**Priority:** Medium""",
                "priority": "normal",
                "status": "open",
                "comments": [
                    "Изучаю библиотеку xlsx для работы с Excel файлами"
                ]
            },
            {
                "summary": "Как разработчик, я хочу видеть детальную информацию об ошибках в логах",
                "description": """**User Story:**
Как разработчик, я хочу видеть детальную информацию об ошибках в логах, чтобы быстро находить и исправлять проблемы.

**Acceptance Criteria:**
- [ ] Расширенная информация об ошибках (стек-трейс, контекст)
- [ ] Фильтрация логов по уровню важности
- [ ] Поиск по ключевым словам
- [ ] Экспорт логов в текстовый файл

**Technical Notes:**
- Интеграция с Sentry для отслеживания ошибок
- Добавить структурированное логирование
- Реализовать полнотекстовый поиск

**Story Points:** 4
**Priority:** High""",
                "priority": "critical",
                "status": "inProgress",
                "comments": [
                    "Настроил интеграцию с Sentry",
                    "Добавил структурированное логирование. Теперь нужно улучшить UI для просмотра логов"
                ]
            },
            {
                "summary": "Как пользователь, я хочу получать уведомления о важных событиях",
                "description": """**User Story:**
Как пользователь, я хочу получать уведомления о важных событиях, чтобы быть в курсе изменений в системе.

**Acceptance Criteria:**
- [ ] Настройки уведомлений в профиле пользователя
- [ ] Push-уведомления в браузере
- [ ] Email-уведомления для критических событий
- [ ] Возможность отписаться от уведомлений

**Technical Notes:**
- Использовать Web Push API для браузерных уведомлений
- Интеграция с email-сервисом (SendGrid)
- Система шаблонов для уведомлений

**Story Points:** 6
**Priority:** Medium""",
                "priority": "normal",
                "status": "open",
                "comments": [
                    "Исследую Web Push API для реализации браузерных уведомлений"
                ]
            },
            {
                "summary": "Как тестировщик, я хочу автоматизировать тестирование API",
                "description": """**User Story:**
Как тестировщик, я хочу автоматизировать тестирование API, чтобы ускорить процесс проверки функциональности.

**Acceptance Criteria:**
- [ ] Написать тесты для всех основных API endpoints
- [ ] Интеграция с CI/CD pipeline
- [ ] Генерация отчетов о покрытии тестами
- [ ] Тесты для позитивных и негативных сценариев

**Technical Notes:**
- Использовать pytest для написания тестов
- Интеграция с GitHub Actions
- Генерация отчетов в формате HTML

**Story Points:** 4
**Priority:** Low""",
                "priority": "minor",
                "status": "open",
                "comments": [
                    "Начинаю изучение pytest для автоматизации тестирования API"
                ]
            },
            {
                "summary": "Как дизайнер, я хочу улучшить мобильную версию приложения",
                "description": """**User Story:**
Как дизайнер, я хочу улучшить мобильную версию приложения, чтобы пользователи могли комфортно работать с телефонов.

**Acceptance Criteria:**
- [ ] Адаптивный дизайн для всех экранов
- [ ] Touch-friendly интерфейс
- [ ] Оптимизация производительности на мобильных устройствах
- [ ] Поддержка жестов (свайп, пинч)

**Technical Notes:**
- Использовать CSS Grid и Flexbox для адаптивности
- Оптимизация изображений для мобильных устройств
- Добавить поддержку PWA

**Story Points:** 5
**Priority:** Medium""",
                "priority": "normal",
                "status": "inProgress",
                "comments": [
                    "Создал макеты для мобильной версии",
                    "Начинаю реализацию адаптивного дизайна"
                ]
            },
            {
                "summary": "Как DevOps инженер, я хочу настроить мониторинг системы",
                "description": """**User Story:**
Как DevOps инженер, я хочу настроить мониторинг системы, чтобы отслеживать производительность и доступность.

**Acceptance Criteria:**
- [ ] Мониторинг CPU, RAM, дискового пространства
- [ ] Алерты при превышении пороговых значений
- [ ] Дашборд с метриками в Grafana
- [ ] Логирование всех системных событий

**Technical Notes:**
- Настройка Prometheus для сбора метрик
- Интеграция с Grafana для визуализации
- Настройка алертов в AlertManager

**Story Points:** 7
**Priority:** High""",
                "priority": "critical",
                "status": "open",
                "comments": [
                    "Изучаю возможности Prometheus для мониторинга"
                ]
            },
            {
                "summary": "Как пользователь, я хочу искать информацию по всему приложению",
                "description": """**User Story:**
Как пользователь, я хочу искать информацию по всему приложению, чтобы быстро находить нужные данные.

**Acceptance Criteria:**
- [ ] Глобальный поиск по всем разделам
- [ ] Автодополнение при вводе
- [ ] Фильтры по типам контента
- [ ] История поисковых запросов

**Technical Notes:**
- Интеграция с Elasticsearch для полнотекстового поиска
- Реализация автодополнения
- Кэширование результатов поиска

**Story Points:** 6
**Priority:** Medium""",
                "priority": "normal",
                "status": "open",
                "comments": [
                    "Исследую возможности Elasticsearch для реализации поиска"
                ]
            },
            {
                "summary": "Как администратор, я хочу управлять правами доступа пользователей",
                "description": """**User Story:**
Как администратор, я хочу управлять правами доступа пользователей, чтобы обеспечить безопасность системы.

**Acceptance Criteria:**
- [ ] Создание и редактирование ролей
- [ ] Назначение ролей пользователям
- [ ] Просмотр истории изменений прав доступа
- [ ] Уведомления о подозрительной активности

**Technical Notes:**
- Реализация RBAC (Role-Based Access Control)
- Аудит изменений прав доступа
- Интеграция с системой уведомлений

**Story Points:** 8
**Priority:** High""",
                "priority": "critical",
                "status": "inProgress",
                "comments": [
                    "Спроектировал структуру ролей и разрешений",
                    "Начинаю реализацию RBAC системы"
                ]
            },
            {
                "summary": "Как аналитик, я хочу видеть аналитику использования приложения",
                "description": """**User Story:**
Как аналитик, я хочу видеть аналитику использования приложения, чтобы понимать поведение пользователей.

**Acceptance Criteria:**
- [ ] Дашборд с ключевыми метриками
- [ ] Графики активности пользователей
- [ ] Анализ популярных функций
- [ ] Экспорт данных для дальнейшего анализа

**Technical Notes:**
- Интеграция с Google Analytics или аналогичным сервисом
- Создание кастомных событий
- Реализация внутренней аналитики

**Story Points:** 5
**Priority:** Low""",
                "priority": "minor",
                "status": "open",
                "comments": [
                    "Изучаю возможности Google Analytics для интеграции"
                ]
            }
        ]
        
        created_issues = []
        
        # Создаем задачи
        for task in demo_tasks:
            issue = self.create_issue(
                summary=task["summary"],
                description=task["description"],
                priority=task["priority"]
            )
            
            if issue:
                created_issues.append({
                    "issue": issue,
                    "task": task
                })
            
            # Небольшая пауза между запросами
            time.sleep(1)
        
        print("\n" + "=" * 60)
        print("💬 Добавление комментариев к задачам...")
        
        # Добавляем комментарии
        for item in created_issues:
            issue = item["issue"]
            task = item["task"]
            
            for comment in task.get("comments", []):
                self.add_comment(issue["key"], comment)
                time.sleep(0.5)
        
        print("\n" + "=" * 60)
        print("🔄 Изменение статусов задач...")
        
        # Изменяем статусы
        for item in created_issues:
            issue = item["issue"]
            task = item["task"]
            
            if task.get("status") == "inProgress":
                self.change_status(issue["key"], "inProgress")
                time.sleep(0.5)
        
        print("\n" + "=" * 60)
        print("🎉 Демонстрационные задачи созданы успешно!")
        print(f"📊 Создано задач: {len(created_issues)}")
        print(f"📋 Очередь: {self.queue_key}")
        print(f"🔗 Ссылка: https://tracker.yandex.ru/{self.queue_key}")
        
        return created_issues

def main():
    """Основная функция"""
    print("🤖 AI-Tracker - Создание демонстрационных данных")
    print("=" * 60)
    
    # Проверяем переменные окружения
    if not os.getenv('YANDEX_TRACKER_TOKEN'):
        print("❌ Ошибка: YANDEX_TRACKER_TOKEN не найден в .env файле")
        return
    
    if not os.getenv('YANDEX_CLOUD_ORG_ID'):
        print("❌ Ошибка: YANDEX_CLOUD_ORG_ID не найден в .env файле")
        return
    
    # Создаем демонстрационные данные
    creator = DemoDataCreator()
    creator.create_demo_tasks()

if __name__ == "__main__":
    main() 