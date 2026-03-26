from fastapi import APIRouter, HTTPException, status
from fastapi.responses import JSONResponse
from app.core.config import settings
from app.schemas.ai import GenerationRequest, GenerationResponse, AIProvider
from app.services.ai_service import ai_service
from enum import Enum
import logging

router = APIRouter()
logger = logging.getLogger(__name__)

@router.post(
    "/generate",
    response_model=GenerationResponse,
    summary="Генерация текста с помощью AI",
    description="Принимает промпт и возвращает сгенерированный текст от выбранного провайдера AI"
)
async def generate_text(request: GenerationRequest):
    """
    Генерация текста через AI API
    
    - **prompt**: Текст для генерации
    - **system_prompt**: Системный промпт (опционально)
    - **max_tokens**: Максимальное количество токенов (опционально)
    - **temperature**: Температура генерации (опционально)
    - **provider**: Провайдер AI (huggingface, openai, deepseek)
    """
    try:
        logger.info(f"Generating text with provider: {request.provider}")

        # Формируем данные для запроса
        request_data = request.dict()

        # Нормализуем Enum-поля (например, `provider`) в простые значения
        try:
            prov = request_data.get("provider")
            if isinstance(prov, Enum):
                request_data["provider"] = prov.value
        except Exception:
            # на случай неожиданных типов — просто пропускаем
            pass

        # Вызываем сервис генерации
        result = await ai_service.generate_text(request_data)

        if not result.get("success"):
            # логируем детально для диагностики
            logger.error("AI generation failed: %s", result)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=result.get("error", "AI generation failed")
            )

        # В режиме отладки возвращаем сырой результат для облегчённой диагностики
        if settings.DEBUG:
            return JSONResponse(content=result, status_code=200)

        # Попытка явно собрать модель ответа и зафиксировать возможные ошибки
        try:
            return GenerationResponse(**result)
        except Exception as e:
            logger.exception("Failed to build GenerationResponse; result=%s", result)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Response build error: {str(e)}"
            )

    except ValueError as e:
        logger.warning("Bad request: %s", str(e))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        # логируем полную трассировку
        logger.exception("Unexpected error while generating text")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )

@router.get("/providers")
async def get_available_providers():
    """Получить список доступных AI провайдеров"""
    return {
        "providers": [
            {
                "id": "huggingface",
                "name": "Hugging Face",
                "description": "Бесплатные модели через Inference API",
                "needs_key": True
            },
            {
                "id": "openai",
                "name": "OpenAI Compatible",
                "description": "OpenAI-совместимые API (OpenRouter, LocalAI)",
                "needs_key": True
            },
            {
                "id": "deepseek",
                "name": "DeepSeek",
                "description": "DeepSeek AI с бесплатным тарифом",
                "needs_key": True
            }
            ,
            {
                "id": "gigachat",
                "name": "Giga Chat",
                "description": "Giga Chat (OpenAI-compatible)",
                "needs_key": True
            }
        ]
    }