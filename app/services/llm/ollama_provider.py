"""
Ollama LLM-провайдер
"""

import logging
import httpx
from typing import Dict, Any, Optional
from .base import BaseLLMProvider

logger = logging.getLogger(__name__)


class OllamaProvider(BaseLLMProvider):
    """Провайдер для Ollama (локальный LLM)"""
    
    def __init__(self, config: Dict[str, Any]):
        """
        Инициализация Ollama провайдера
        
        Args:
            config: Конфигурация с ключами:
                - base_url: URL Ollama сервера
                - model: Название модели
                - timeout: Таймаут запросов
        """
        super().__init__("ollama", config)
        
        self.base_url = config.get('base_url', 'http://ollama:11434')
        self.model = config.get('model', 'hf.co/Vikhrmodels/Vikhr-Gemma-2B-instruct-GGUF:Q3_K_L')
        
        # Убираем trailing slash
        self.base_url = self.base_url.rstrip('/')
        
        try:
            self._check_model_availability()
        except ValueError:
            logger.warning(f"Модель {self.model} не найдена в Ollama при инициализации. Будет предпринята попытка загрузки позже.")
        
        logger.info(f"Ollama провайдер настроен: {self.base_url}, модель: {self.model}")
    
    def _check_model_availability(self):
        """Проверить доступность модели в Ollama"""
        try:
            # Проверяем, что Ollama доступен
            with httpx.Client(timeout=10) as client:
                response = client.get(f"{self.base_url}/api/tags")
                if response.status_code != 200:
                    raise ConnectionError(f"Ollama недоступен: {response.status_code}")
                
                # Получаем список доступных моделей
                models_data = response.json()
                available_models = [model['name'] for model in models_data.get('models', [])]
                
                logger.info(f"Доступные модели Ollama: {available_models}")
                
                # Проверяем, есть ли наша модель (учитываем возможные варианты названий)
                model_found = False
                for available_model in available_models:
                    # Убираем префикс hf.co/ и суффикс :Q3_K_L для сравнения
                    clean_available = available_model.replace('hf.co/', '').split(':')[0]
                    clean_self = self.model.replace('hf.co/', '').split(':')[0]
                    
                    if clean_available == clean_self:
                        model_found = True
                        logger.info(f"Модель найдена: {available_model} соответствует {self.model}")
                        break
                
                if not model_found:
                    logger.error(f"Модель {self.model} не найдена в Ollama!")
                    logger.error(f"Доступные модели: {available_models}")
                    logger.error("Для установки модели выполните: ollama pull hf.co/Vikhrmodels/Vikhr-Gemma-2B-instruct-GGUF:Q3_K_L")
                    raise ValueError(f"Модель {self.model} не установлена в Ollama")
                
                logger.info(f"Модель {self.model} найдена и доступна")
                
        except Exception as e:
            logger.error(f"Ошибка при проверке модели Ollama: {e}")
            raise
    
    async def generate(self, prompt: str, **kwargs) -> str:
        """
        Генерировать ответ через Ollama API
        
        Args:
            prompt: Промт для генерации
            **kwargs: Дополнительные параметры (temperature, top_p, etc.)
            
        Returns:
            Сгенерированный ответ
            
        Raises:
            Exception: При ошибке API
        """
        try:
            logger.info(f"Отправляем запрос в Ollama: {self.model}")
            logger.info(f"Таймаут запроса: {self.timeout} секунд")
            logger.debug(f"Промт (первые 100 символов): {prompt[:100]}...")
            logger.debug(f"Полный промт: {prompt}")
            
            # Параметры генерации
            generation_params = {
                "model": self.model,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": kwargs.get('temperature', 0.7),
                    "top_p": kwargs.get('top_p', 0.9)
                }
            }
            
            logger.info(f"Параметры генерации: {generation_params}")
            
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                logger.info(f"Отправляем POST запрос на {self.base_url}/api/generate")
                response = await client.post(
                    f"{self.base_url}/api/generate",
                    json=generation_params
                )
                
                logger.info(f"Получен ответ от Ollama: {response.status_code}")
                
                if response.status_code == 200:
                    result = response.json()
                    response_text = result.get("response", "").strip()
                    
                    logger.info(f"Ollama ответ получен, длина: {len(response_text)} символов")
                    logger.debug(f"Полный ответ: {response_text}")
                    return response_text
                else:
                    error_msg = f"Ошибка Ollama API: {response.status_code} - {response.text}"
                    logger.error(error_msg)
                    raise Exception(error_msg)
                    
        except Exception as e:
            logger.error(f"Ошибка при вызове Ollama API: {e}")
            logger.error(f"Детали ошибки: {type(e).__name__}: {str(e)}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            raise
    
    def is_available(self) -> bool:
        """
        Проверить доступность Ollama
        
        Returns:
            True если Ollama доступен (локальный сервис)
        """
        # Ollama работает локально, поэтому считаем доступным
        return True
    
    async def health_check(self) -> Dict[str, Any]:
        """Проверка здоровья Ollama"""
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.get(f"{self.base_url}/api/tags")
                
                if response.status_code == 200:
                    models_data = response.json()
                    available_models = [model['name'] for model in models_data.get('models', [])]
                    
                    return {
                        "status": "healthy",
                        "model": self.model,
                        "model_available": self.model in available_models,
                        "available_models": available_models,
                        "base_url": self.base_url
                    }
                else:
                    return {
                        "status": "unhealthy",
                        "error": f"HTTP {response.status_code}",
                        "base_url": self.base_url
                    }
                    
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
                "base_url": self.base_url
            }
    
    async def list_models(self) -> list[str]:
        """
        Получить список доступных моделей
        
        Returns:
            Список названий моделей
        """
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(f"{self.base_url}/api/tags")
                if response.status_code == 200:
                    result = response.json()
                    return [model['name'] for model in result.get('models', [])]
                else:
                    logger.error(f"Ошибка получения моделей: {response.status_code}")
                    return []
        except Exception as e:
            logger.error(f"Ошибка при получении списка моделей: {e}")
            return []
    
    async def pull_model(self, model_name: str) -> bool:
        """
        Загрузить модель
        
        Args:
            model_name: Название модели для загрузки
            
        Returns:
            True если модель загружена успешно
        """
        try:
            logger.info(f"Загружаем модель: {model_name}")
            
            async with httpx.AsyncClient(timeout=300.0) as client:  # Долгий таймаут для загрузки
                response = await client.post(
                    f"{self.base_url}/api/pull",
                    json={"name": model_name}
                )
                
                if response.status_code == 200:
                    logger.info(f"Модель {model_name} загружена успешно")
                    return True
                else:
                    logger.error(f"Ошибка загрузки модели: {response.status_code}")
                    return False
                    
        except Exception as e:
            logger.error(f"Ошибка при загрузке модели {model_name}: {e}")
            return False
    
    async def ensure_model_available(self):
        """Проверить и при необходимости загрузить модель Ollama"""
        try:
            self._check_model_availability()
        except ValueError:
            logger.warning(f"Модель {self.model} не найдена. Пытаюсь загрузить автоматически...")
            success = await self.pull_model(self.model)
            if success:
                logger.info(f"Модель {self.model} загружена успешно")
                # Ждём инициализации модели в Ollama
                import asyncio
                await asyncio.sleep(10)
                # Повторно проверяем доступность
                try:
                    self._check_model_availability()
                    logger.info(f"Модель {self.model} успешно инициализирована")
                except ValueError:
                    raise ValueError(f"Модель {self.model} загружена, но не инициализирована в Ollama")
            else:
                raise ValueError(f"Не удалось загрузить модель {self.model}")
        except Exception as e:
            logger.error(f"Ошибка при проверке доступности модели: {e}")
            raise 