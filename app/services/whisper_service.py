import logging
import httpx
import tempfile
import os
from typing import Optional

logger = logging.getLogger(__name__)


class WhisperService:
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip('/')
        
    async def transcribe_audio(self, audio_data: bytes, language: str = "ru") -> Optional[str]:
        """Транскрибировать аудио в текст"""
        try:
            logger.info(f"Отправляем аудио на транскрипцию в Whisper (размер: {len(audio_data)} байт)")
            
            async with httpx.AsyncClient() as client:
                # Создаем временный файл для аудио
                with tempfile.NamedTemporaryFile(delete=False, suffix='.ogg') as temp_file:
                    temp_file.write(audio_data)
                    temp_file_path = temp_file.name
                
                try:
                    # Отправляем файл на транскрипцию
                    with open(temp_file_path, 'rb') as audio_file:
                        files = {'audio_file': ('audio.ogg', audio_file, 'audio/ogg')}
                        data = {'language': language}
                        
                        response = await client.post(
                            f"{self.base_url}/asr",
                            files=files,
                            data=data,
                            timeout=60.0
                        )
                    
                    if response.status_code == 200:
                        result = response.json()
                        transcription = result.get('transcription', '')
                        logger.info(f"Транскрипция успешна: {transcription[:100]}...")
                        return transcription
                    else:
                        logger.error(f"Ошибка Whisper API: {response.status_code} - {response.text}")
                        return None
                        
                finally:
                    # Удаляем временный файл
                    if os.path.exists(temp_file_path):
                        os.unlink(temp_file_path)
                        
        except Exception as e:
            logger.error(f"Ошибка при транскрипции аудио: {e}")
            return None
    
    def is_available(self) -> bool:
        """Проверить доступность Whisper сервиса"""
        try:
            import httpx
            response = httpx.get(f"{self.base_url}/health", timeout=5.0)
            return response.status_code == 200
        except Exception:
            return False 