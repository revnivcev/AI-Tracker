"""
Базовый класс для LLM-провайдеров
"""

import logging
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


class BaseLLMProvider(ABC):
    """Базовый класс для всех LLM-провайдеров"""
    
    def __init__(self, name: str, config: Dict[str, Any]):
        """
        Инициализация провайдера
        
        Args:
            name: Название провайдера
            config: Конфигурация провайдера
        """
        self.name = name
        self.config = config
        self.timeout = config.get('timeout', 60)
        
        logger.info(f"Инициализирован LLM-провайдер: {name}")
    
    @abstractmethod
    async def generate(self, prompt: str, **kwargs) -> str:
        """
        Генерировать ответ на промт
        
        Args:
            prompt: Промт для генерации
            **kwargs: Дополнительные параметры
            
        Returns:
            Сгенерированный ответ
            
        Raises:
            Exception: При ошибке генерации
        """
        pass
    
    @abstractmethod
    def is_available(self) -> bool:
        """
        Проверить доступность провайдера
        
        Returns:
            True если провайдер доступен, False иначе
        """
        pass
    
    @abstractmethod
    async def health_check(self) -> bool:
        """
        Проверить здоровье провайдера
        
        Returns:
            True если провайдер здоров, False иначе
        """
        pass
    
    def get_info(self) -> Dict[str, Any]:
        """
        Получить информацию о провайдере
        
        Returns:
            Словарь с информацией о провайдере
        """
        return {
            "name": self.name,
            "type": self.__class__.__name__,
            "available": self.is_available(),
            "config": {k: v for k, v in self.config.items() if k != 'api_key'}
        }
    
    async def generate_with_fallback(self, prompt: str, fallback_response: str = "", **kwargs) -> str:
        """
        Генерировать ответ с fallback
        
        Args:
            prompt: Промт для генерации
            fallback_response: Ответ по умолчанию при ошибке
            **kwargs: Дополнительные параметры
            
        Returns:
            Сгенерированный ответ или fallback
        """
        try:
            return await self.generate(prompt, **kwargs)
        except Exception as e:
            logger.error(f"Ошибка генерации в {self.name}: {e}")
            return fallback_response 