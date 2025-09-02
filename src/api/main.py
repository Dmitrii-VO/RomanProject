"""
Основной FastAPI приложение для веб API и webhook'ов
"""
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Dict
import os

from utils.logger import app_logger
from src.ai.consultant import AmberAIConsultant
from src.integrations.yukassa import YuKassaClient

# Создание FastAPI приложения
app = FastAPI(
    title="Amber AI Consultant API",
    description="API для ИИ консультанта янтарного магазина",
    version="0.1.0"
)

# Настройка CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Инициализация компонентов
ai_consultant = AmberAIConsultant()
yukassa_client = YuKassaClient()


class ChatMessage(BaseModel):
    """Модель сообщения чата"""
    message: str
    user_id: str


class PaymentRequest(BaseModel):
    """Модель запроса на создание платежа"""
    amount: float
    description: str
    customer_email: str = None


@app.get("/")
async def root():
    """Корневая страница API"""
    return {
        "message": "Amber AI Consultant API",
        "status": "active",
        "version": "0.1.0"
    }


@app.get("/health")
async def health_check():
    """Проверка здоровья сервиса"""
    return {
        "status": "healthy",
        "ai_consultant": "ready",
        "payment_system": "ready"
    }


@app.post("/chat")
async def chat_endpoint(message: ChatMessage):
    """
    Эндпоинт для общения с ИИ консультантом
    
    Args:
        message: Сообщение от пользователя
        
    Returns:
        Ответ ИИ консультанта
    """
    try:
        app_logger.info(f"API запрос от пользователя {message.user_id}")
        
        response = await ai_consultant.process_message(message.message)
        
        return {
            "response": response,
            "user_id": message.user_id,
            "status": "success"
        }
        
    except Exception as e:
        app_logger.error(f"Ошибка в chat API: {e}")
        raise HTTPException(status_code=500, detail="Внутренняя ошибка сервера")


@app.post("/payment/create")
async def create_payment(payment_request: PaymentRequest):
    """
    Создание платежа через ЮKassa
    
    Args:
        payment_request: Данные для создания платежа
        
    Returns:
        Данные о созданном платеже
    """
    try:
        payment = await yukassa_client.create_payment(
            amount=payment_request.amount,
            description=payment_request.description,
            customer_email=payment_request.customer_email
        )
        
        if payment:
            return {
                "payment_id": payment["id"],
                "payment_url": payment["confirmation"]["confirmation_url"],
                "amount": payment["amount"]["value"],
                "status": payment["status"]
            }
        else:
            raise HTTPException(status_code=400, detail="Не удалось создать платеж")
            
    except Exception as e:
        app_logger.error(f"Ошибка создания платежа: {e}")
        raise HTTPException(status_code=500, detail="Ошибка при создании платежа")


@app.post("/webhook/yukassa")
async def yukassa_webhook(webhook_data: Dict):
    """
    Webhook для получения уведомлений от ЮKassa
    
    Args:
        webhook_data: Данные от ЮKassa
    """
    try:
        app_logger.info(f"Получен webhook от ЮKassa: {webhook_data}")
        
        # TODO: Обработка различных событий платежа
        event_type = webhook_data.get("event")
        payment_object = webhook_data.get("object")
        
        if event_type == "payment.succeeded":
            payment_id = payment_object.get("id")
            app_logger.info(f"Платеж {payment_id} успешно завершен")
            # TODO: Обновить статус заказа в системе
        
        return {"status": "received"}
        
    except Exception as e:
        app_logger.error(f"Ошибка обработки webhook: {e}")
        raise HTTPException(status_code=500, detail="Ошибка обработки webhook")


if __name__ == "__main__":
    import uvicorn
    
    port = int(os.getenv("PORT", 8000))
    host = os.getenv("HOST", "0.0.0.0")
    
    app_logger.info(f"Запуск FastAPI сервера на {host}:{port}")
    
    uvicorn.run(
        "src.api.main:app",
        host=host,
        port=port,
        reload=os.getenv("DEBUG", "False").lower() == "true"
    )