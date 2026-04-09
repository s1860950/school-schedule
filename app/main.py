from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from app.api.endpoints import ai
from app.core.config import settings
import uvicorn
import logging
import traceback
import os

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    docs_url="/docs",
    redoc_url="/redoc"
)

# Настройка CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # В продакшене укажите конкретные домены
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Подключаем роутеры
app.include_router(ai.router, prefix="/api/v1", tags=["AI"])

@app.get("/")
async def root():
    """Возвращает главную HTML страницу приложения"""
    template_path = os.path.join(os.path.dirname(__file__), "templates", "index.html")
    if os.path.exists(template_path):
        return FileResponse(template_path, media_type="text/html")
    return {
        "message": "Добро пожаловать в AI API",
        "version": settings.APP_VERSION,
        "docs": "/docs",
        "endpoints": {
            "generate_text": "POST /api/v1/generate",
            "generate_excel": "POST /api/v1/generate-excel",
            "health": "GET /health"
        }
    }

@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "AI Backend"}

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=settings.PORT,
        reload=settings.DEBUG
    )

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

@app.exception_handler(Exception)
async def generic_exception_handler(request, exc):
    logger.error(f"Unhandled exception: {exc}")
    logger.error(traceback.format_exc())
    return JSONResponse(
        status_code=500,
        content={"detail": f"Internal server error: {str(exc)}"}
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request, exc):
    detail = exc.errors()
    content_type = request.headers.get("content-type", "")

    if request.url.path == "/api/v1/generate":
        hint = (
            "Use JSON like {\"prompt\": \"...\", \"provider\": \"yandexgpt\"} "
            "or send plain text with Content-Type: text/plain."
        )
        if content_type and not any(
            marker in content_type.lower()
            for marker in (
                "application/json",
                "text/plain",
                "application/x-www-form-urlencoded",
                "multipart/form-data",
            )
        ):
            return JSONResponse(
                status_code=415,
                content={
                    "detail": "Unsupported media type for /api/v1/generate.",
                    "hint": hint,
                },
            )

        return JSONResponse(
            status_code=422,
            content={
                "detail": detail,
                "hint": hint,
            },
        )

    return JSONResponse(status_code=422, content={"detail": detail})
