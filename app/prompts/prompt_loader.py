"""
Загрузчик промтов с поддержкой jinja2 шаблонизации
"""

import os
import logging
from pathlib import Path
from typing import Dict, Any, Optional
from jinja2 import Environment, FileSystemLoader, Template

logger = logging.getLogger(__name__)


class PromptLoader:
    """Загрузчик и рендерер промтов с поддержкой jinja2"""
    
    def __init__(self, prompts_dir: Optional[str] = None):
        """
        Инициализация загрузчика промтов
        
        Args:
            prompts_dir: Путь к директории с промтами (по умолчанию app/prompts/templates)
        """
        if prompts_dir is None:
            # Путь относительно корня проекта
            prompts_dir = Path(__file__).parent / "templates"
        
        self.prompts_dir = str(prompts_dir)
        self._ensure_prompts_dir()
        
        # Инициализируем jinja2 environment
        self.env = Environment(
            loader=FileSystemLoader(self.prompts_dir),
            autoescape=False,  # Для промтов не нужен autoescape
            trim_blocks=True,
            lstrip_blocks=True
        )
        
        # Кэш для загруженных шаблонов
        self._template_cache: Dict[str, Template] = {}
        
        logger.info(f"PromptLoader инициализирован с директорией: {self.prompts_dir}")
    
    def _ensure_prompts_dir(self):
        """Создать директорию с промтами, если её нет"""
        if not Path(self.prompts_dir).exists():
            Path(self.prompts_dir).mkdir(parents=True, exist_ok=True)
            logger.info(f"Создана директория для промтов: {self.prompts_dir}")
    
    def load_prompt(self, template_name: str, **kwargs) -> str:
        """
        Загрузить и отрендерить промт
        
        Args:
            template_name: Имя файла шаблона (например, 'create_task.md')
            **kwargs: Переменные для подстановки в шаблон
            
        Returns:
            Отрендеренный промт
            
        Raises:
            FileNotFoundError: Если файл шаблона не найден
            jinja2.TemplateError: При ошибке рендеринга
        """
        try:
            # Проверяем кэш
            if template_name not in self._template_cache:
                template = self.env.get_template(template_name)
                self._template_cache[template_name] = template
                logger.debug(f"Загружен шаблон: {template_name}")
            
            template = self._template_cache[template_name]
            rendered = template.render(**kwargs)
            
            logger.debug(f"Отрендерен промт: {template_name}")
            return rendered.strip()
            
        except Exception as e:
            logger.error(f"Ошибка при загрузке промта {template_name}: {e}")
            raise
    
    def get_available_prompts(self) -> list[str]:
        """Получить список доступных промтов"""
        try:
            return [f.name for f in Path(self.prompts_dir).glob("*.md") if f.is_file()]
        except Exception as e:
            logger.error(f"Ошибка при получении списка промтов: {e}")
            return []
    
    def reload_templates(self):
        """Перезагрузить все шаблоны (очистить кэш)"""
        self._template_cache.clear()
        logger.info("Кэш шаблонов очищен")
    
    def validate_template(self, template_name: str, **kwargs) -> bool:
        """
        Проверить, что шаблон корректно рендерится с заданными переменными
        
        Args:
            template_name: Имя шаблона
            **kwargs: Переменные для проверки
            
        Returns:
            True если шаблон валиден, False иначе
        """
        try:
            self.load_prompt(template_name, **kwargs)
            return True
        except Exception as e:
            logger.error(f"Шаблон {template_name} невалиден: {e}")
            return False 