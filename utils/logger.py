"""
Модуль настройки логирования для ИИ консультанта янтарного магазина
"""
import os
from loguru import logger
from dotenv import load_dotenv

load_dotenv()

def setup_logger():
    """Настройка системы логирования"""
    
    # Получаем уровень логирования из переменных окружения
    log_level = os.getenv("LOG_LEVEL", "INFO")
    debug = os.getenv("DEBUG", "False").lower() == "true"
    
    # Удаляем стандартный обработчик loguru
    logger.remove()
    
    # Настраиваем вывод в консоль
    if debug:
        logger.add(
            sink=lambda msg: print(msg, end=""),
            format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
            level=log_level,
            colorize=True
        )
    else:
        logger.add(
            sink=lambda msg: print(msg, end=""),
            format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {message}",
            level=log_level,
            colorize=False
        )
    
    # Настраиваем логирование в файл
    logger.add(
        "logs/bot.log",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
        level=log_level,
        rotation="10 MB",  # Ротация при достижении 10MB
        retention="30 days",  # Хранение логов 30 дней
        compression="zip",  # Сжатие старых логов
        encoding="utf-8"
    )
    
    # Отдельный файл для ошибок
    logger.add(
        "logs/errors.log",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
        level="ERROR",
        rotation="5 MB",
        retention="60 days",
        compression="zip",
        encoding="utf-8"
    )
    
    # Отдельный файл для диалогов с клиентами
    logger.add(
        "logs/conversations.log",
        format="{time:YYYY-MM-DD HH:mm:ss} | {extra[user_id]} | {extra[chat_type]} | {message}",
        filter=lambda record: "conversation" in record["extra"],
        rotation="50 MB",
        retention="1 year",  # Диалоги храним год для аналитики
        compression="zip",
        encoding="utf-8"
    )
    
    logger.info("Система логирования инициализирована")
    return logger

def log_conversation(user_id: int, chat_type: str, message: str):
    """
    Логирование диалогов с клиентами
    
    Args:
        user_id: ID пользователя
        chat_type: Тип сообщения (user_message, bot_response, escalation)
        message: Текст сообщения
    """
    logger.bind(conversation=True, user_id=user_id, chat_type=chat_type).info(message)

# Создаем экземпляр логгера для использования в других модулях
app_logger = setup_logger()