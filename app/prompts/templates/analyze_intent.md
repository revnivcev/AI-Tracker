# Анализ намерений

**Текст:** {{ user_text }}
**Очереди:** {{ ', '.join(available_queues) }}
**Приоритеты:** {{ ', '.join(available_priorities) }}

**Задача:** Определи намерение и извлеки данные для создания задачи.

**Формат ответа:**
```json
{
    "wants_to_create_task": true,
    "has_sufficient_data": true,
    "confidence": 0.95,
    "extracted_data": {
        "summary": "Название задачи",
        "description": "Описание",
        "queue": "DEV",
        "priority": "Высокий",
        "assignee": null,
        "deadline": "2025-07-06",
        "tags": ["bug", "auth"],
        "type": "bug"
    },
    "missing_data": [],
    "reasoning": "Объяснение"
}
```

**Правила:**
- Ищи: "создай", "баг", "ошибка", "нужно", "требуется"
- Минимум: название (3+ слов) + контекст
- Типы: bug, task, feature, epic
- Приоритеты: Критический > Высокий > Средний > Низкий
- Извлекай реальную информацию из текста

**Пример:**
Вход: "Сбор бизнес-требований с заказчика (т-банк). Нужно провести интервью со всеми стейкхолдерами и сформировать базу с документацией Дедлайн 06.07.2025"

Выход:
```json
{
    "wants_to_create_task": true,
    "has_sufficient_data": true,
    "confidence": 0.98,
    "extracted_data": {
        "summary": "Сбор бизнес-требований с заказчика (т-банк)",
        "description": "Провести интервью со всеми стейкхолдерами и сформировать базу с документацией",
        "queue": "ANALYTICS",
        "priority": "Высокий",
        "assignee": null,
        "deadline": "2025-07-06",
        "tags": ["requirements", "stakeholders"],
        "type": "task"
    },
    "missing_data": [],
    "reasoning": "Четкое описание задачи с контекстом и дедлайном"
}
``` 