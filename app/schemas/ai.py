from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from enum import Enum

class AIProvider(str, Enum):
    HUGGINGFACE = "huggingface"
    OPENAI = "openai"
    DEEPSEEK = "deepseek"
    GIGACHAT = "gigachat"

class GenerationRequest(BaseModel):
    prompt: str = Field(..., min_length=1, max_length=2000, description="Текст для генерации")
    system_prompt: Optional[str] = Field(
        default="Ты - полезный AI ассистент. Отвечай на русском языке.",
        description="Системный промпт для настройки поведения AI"
    )
    max_tokens: Optional[int] = Field(default=500, ge=1, le=2000, description="Максимальное количество токенов")
    temperature: Optional[float] = Field(default=0.7, ge=0.1, le=1.0, description="Температура генерации")
    provider: Optional[AIProvider] = Field(default=AIProvider.GIGACHAT, description="Провайдер AI")
    
    class Config:
        json_schema_extra = {
            "example": {
                "prompt": "Расскажи мне о преимуществах искусственного интеллекта",
                "system_prompt": "Ты - эксперт по искусственному интеллекту.",
                "max_tokens": 300,
                "temperature": 0.7,
                "provider": "gigachat"
            }
        }

class GenerationResponse(BaseModel):
    success: bool
    generated_text: Optional[str] = None
    provider: str
    model: Optional[str] = None
    tokens_used: Optional[int] = None
    error: Optional[str] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "generated_text": "Искусственный интеллект имеет множество преимуществ...",
                "provider": "gigachat",
                "model": "mistralai/Mistral-7B-Instruct-v0.1",
                "tokens_used": 150
            }
        }