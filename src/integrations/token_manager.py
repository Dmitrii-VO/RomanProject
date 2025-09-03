"""
Менеджер токенов для автоматического обновления токенов доступа к внешним API
"""
import os
import json
from typing import Dict, Optional
from datetime import datetime, timedelta
from utils.logger import app_logger


class TokenManager:
    """
    Менеджер для работы с токенами доступа
    """
    
    def __init__(self, tokens_file_path: str = "tokens.json"):
        """
        Инициализация менеджера токенов
        
        Args:
            tokens_file_path: Путь к файлу для хранения токенов
        """
        self.tokens_file_path = tokens_file_path
        self.tokens = self._load_tokens()
        
    def _load_tokens(self) -> Dict:
        """
        Загружает токены из файла
        
        Returns:
            Словарь с токенами
        """
        try:
            if os.path.exists(self.tokens_file_path):
                with open(self.tokens_file_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            app_logger.error(f"Ошибка загрузки токенов: {e}")
            
        return {}
    
    def _save_tokens(self):
        """
        Сохраняет токены в файл
        """
        try:
            with open(self.tokens_file_path, 'w', encoding='utf-8') as f:
                json.dump(self.tokens, f, indent=2, ensure_ascii=False)
        except Exception as e:
            app_logger.error(f"Ошибка сохранения токенов: {e}")
    
    def save_amocrm_tokens(self, access_token: str, refresh_token: str, expires_in: int = 86400):
        """
        Сохраняет токены AmoCRM
        
        Args:
            access_token: Access токен
            refresh_token: Refresh токен  
            expires_in: Время жизни токена в секундах
        """
        expires_at = (datetime.now() + timedelta(seconds=expires_in)).isoformat()
        
        self.tokens['amocrm'] = {
            'access_token': access_token,
            'refresh_token': refresh_token,
            'expires_at': expires_at,
            'updated_at': datetime.now().isoformat()
        }
        
        self._save_tokens()
        app_logger.info("Токены AmoCRM сохранены")
    
    def get_amocrm_access_token(self) -> Optional[str]:
        """
        Получает актуальный access token для AmoCRM
        
        Returns:
            Access token или None если токен отсутствует/истек
        """
        if 'amocrm' not in self.tokens:
            return None
            
        amocrm_data = self.tokens['amocrm']
        expires_at = datetime.fromisoformat(amocrm_data['expires_at'])
        
        # Проверяем, не истек ли токен (с запасом в 5 минут)
        if datetime.now() + timedelta(minutes=5) < expires_at:
            return amocrm_data['access_token']
        
        return None
    
    def get_amocrm_refresh_token(self) -> Optional[str]:
        """
        Получает refresh token для AmoCRM
        
        Returns:
            Refresh token или None
        """
        if 'amocrm' not in self.tokens:
            return None
            
        return self.tokens['amocrm'].get('refresh_token')
    
    def is_amocrm_token_expired(self) -> bool:
        """
        Проверяет истек ли токен AmoCRM
        
        Returns:
            True если токен истек или отсутствует
        """
        if 'amocrm' not in self.tokens:
            return True
            
        amocrm_data = self.tokens['amocrm']
        expires_at = datetime.fromisoformat(amocrm_data['expires_at'])
        
        # Токен считается истекшим за 5 минут до реального истечения
        return datetime.now() + timedelta(minutes=5) >= expires_at
    
    def update_env_file(self, updates: Dict[str, str]):
        """
        Обновляет переменные окружения в .env файле
        
        Args:
            updates: Словарь переменных для обновления
        """
        env_path = '.env'
        if not os.path.exists(env_path):
            app_logger.error("Файл .env не найден")
            return
        
        try:
            # Читаем существующий .env файл
            with open(env_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            # Обновляем переменные
            updated_lines = []
            updated_keys = set()
            
            for line in lines:
                line = line.strip()
                if '=' in line and not line.startswith('#'):
                    key, value = line.split('=', 1)
                    if key in updates:
                        updated_lines.append(f"{key}={updates[key]}\n")
                        updated_keys.add(key)
                    else:
                        updated_lines.append(line + '\n')
                else:
                    updated_lines.append(line + '\n')
            
            # Добавляем новые переменные, которых не было в файле
            for key, value in updates.items():
                if key not in updated_keys:
                    updated_lines.append(f"{key}={value}\n")
            
            # Записываем обновленный файл
            with open(env_path, 'w', encoding='utf-8') as f:
                f.writelines(updated_lines)
                
            app_logger.info(f"Обновлены переменные окружения: {', '.join(updates.keys())}")
            
        except Exception as e:
            app_logger.error(f"Ошибка обновления .env файла: {e}")
    
    def sync_amocrm_tokens_to_env(self):
        """
        Синхронизирует токены AmoCRM с .env файлом
        """
        if 'amocrm' not in self.tokens:
            return
            
        amocrm_data = self.tokens['amocrm']
        updates = {
            'AMOCRM_ACCESS_TOKEN': amocrm_data['access_token'],
            'AMOCRM_REFRESH_TOKEN': amocrm_data['refresh_token']
        }
        
        self.update_env_file(updates)
    
    def get_token_status(self) -> Dict:
        """
        Возвращает статус всех токенов
        
        Returns:
            Словарь со статусом токенов
        """
        status = {}
        
        if 'amocrm' in self.tokens:
            amocrm_data = self.tokens['amocrm']
            expires_at = datetime.fromisoformat(amocrm_data['expires_at'])
            
            status['amocrm'] = {
                'has_tokens': True,
                'expires_at': expires_at.isoformat(),
                'is_expired': self.is_amocrm_token_expired(),
                'time_until_expiry': str(expires_at - datetime.now()) if expires_at > datetime.now() else "Истек"
            }
        else:
            status['amocrm'] = {
                'has_tokens': False,
                'is_expired': True
            }
        
        return status