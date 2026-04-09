# app/core/config.py
import os
from typing import List, Optional
from dotenv import load_dotenv

load_dotenv(override=True)

class Settings:
    # Настройки приложения
    APP_NAME: str = os.getenv("APP_NAME", "AI Backend API")
    APP_VERSION: str = os.getenv("APP_VERSION", "1.0.0")
    PORT: int = int(os.getenv("PORT", "8000"))
    DEBUG: bool = os.getenv("DEBUG", "true").lower() == "true"
    
    # AI провайдеры
    AI_PROVIDER: str = os.getenv("AI_PROVIDER", "yandexgpt")
    
    # Hugging Face
    HUGGINGFACE_API_KEY: Optional[str] = os.getenv("HUGGINGFACE_API_KEY")
    HUGGINGFACE_MODEL: str = os.getenv("HUGGINGFACE_MODEL", "mistralai/Mistral-7B-Instruct-v0.1")
    
    # OpenAI
    OPENAI_API_KEY: Optional[str] = os.getenv("OPENAI_API_KEY")
    OPENAI_API_BASE: str = os.getenv("OPENAI_API_BASE", "https://api.openai.com/v1")
    OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gpt-3.5-turbo")
    
    DEEPSEEK_API_KEY: Optional[str] = os.getenv("DEEPSEEK_API_KEY")
    DEEPSEEK_API_BASE: Optional[str] = os.getenv("DEEPSEEK_API_BASE")
    DEEPSEEK_MODEL: Optional[str] = os.getenv("DEEPSEEK_MODEL")

    # YandexGPT
    YANDEX_API_KEY: Optional[str] = os.getenv("YANDEX_API_KEY")
    YANDEX_IAM_TOKEN: Optional[str] = os.getenv("YANDEX_IAM_TOKEN")
    YANDEX_FOLDER_ID: Optional[str] = os.getenv("YANDEX_FOLDER_ID")
    YANDEX_API_BASE: str = os.getenv("YANDEX_API_BASE", "https://llm.api.cloud.yandex.net/v1")
    YANDEX_MODEL: str = os.getenv("YANDEX_MODEL", "yandexgpt/latest")

    # Giga Chat
    # `GIGA_AUTH_KEY` - Authorization key (Basic) issued by provider; used to request short-lived Access token.
    # If you already have a short-lived Access token, you may set it in `GIGA_API_KEY` instead (token will expire).
    GIGA_AUTH_KEY: Optional[str] = os.getenv("GIGA_AUTH_KEY")
    GIGA_API_KEY: Optional[str] = os.getenv("GIGA_API_KEY")
    GIGA_API_BASE: str = os.getenv("GIGA_API_BASE", "https://gigachat.devices.sberbank.ru/api/v1")
    GIGA_AUTH_URL: str = os.getenv("GIGA_AUTH_URL", "https://ngw.devices.sberbank.ru:9443/api/v2/oauth")
    GIGA_MODEL: str = os.getenv("GIGA_MODEL", "GigaChat")
    # Optional path to a CA bundle file (PEM) to validate GigaChat's self-signed certificate
    # If provided, this path will be passed to HTTP clients / SDK as the CA bundle.
    GIGA_CA_BUNDLE: Optional[str] = os.getenv("GIGA_CA_BUNDLE")
    # Таймауты
    REQUEST_TIMEOUT: int = int(os.getenv("REQUEST_TIMEOUT", "30"))
    MAX_RETRIES: int = int(os.getenv("MAX_RETRIES", "3"))

settings = Settings()
