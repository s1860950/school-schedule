from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field

PROMPT_MAX_LENGTH = 5000
MAX_OUTPUT_TOKENS = 5000


class AIProvider(str, Enum):
    HUGGINGFACE = "huggingface"
    OPENAI = "openai"
    DEEPSEEK = "deepseek"
    YANDEXGPT = "yandexgpt"
    GIGACHAT = "gigachat"


class GenerationRequest(BaseModel):
    prompt: str = Field(
        ...,
        min_length=1,
        max_length=PROMPT_MAX_LENGTH,
        description="Prompt text to generate a response for",
    )
    system_prompt: Optional[str] = Field(
        default="You are a helpful AI assistant. Reply in Russian.",
        description="Optional system prompt",
    )
    max_tokens: Optional[int] = Field(
        default=MAX_OUTPUT_TOKENS,
        ge=1,
        le=MAX_OUTPUT_TOKENS,
        description="Maximum number of generated tokens",
    )
    temperature: Optional[float] = Field(default=0.7, ge=0.1, le=1.0, description="Generation temperature")
    provider: Optional[AIProvider] = Field(default=AIProvider.YANDEXGPT, description="AI provider")

    class Config:
        json_schema_extra = {
            "example": {
                "prompt": "Расскажи мне о преимуществах искусственного интеллекта",
                "system_prompt": "Ты эксперт по искусственному интеллекту.",
                "max_tokens": 300,
                "temperature": 0.1,
                "provider": "yandexgpt",
            }
        }


class GenerationResponse(BaseModel):
    success: bool
    generated_text: Optional[str] = None
    provider: str
    model: Optional[str] = None
    tokens_used: Optional[int] = None
    prompt_tokens: Optional[int] = None
    completion_tokens: Optional[int] = None
    reasoning_tokens: Optional[int] = None
    finish_reason: Optional[str] = None
    alternative_status: Optional[str] = None
    truncated: Optional[bool] = None
    error: Optional[str] = None

    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "generated_text": "Искусственный интеллект помогает автоматизировать рутинные задачи и ускоряет анализ данных.",
                "provider": "yandexgpt",
                "model": "gpt://your-folder-id/yandexgpt/latest",
                "tokens_used": 150,
                "prompt_tokens": 90,
                "completion_tokens": 60,
                "reasoning_tokens": 0,
                "alternative_status": "ALTERNATIVE_STATUS_FINAL",
                "truncated": False,
            }
        }
