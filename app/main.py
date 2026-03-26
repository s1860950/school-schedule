from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.endpoints import ai
from app.core.config import settings
import uvicorn
import logging
import traceback

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
    return {
        "message": "Добро пожаловать в AI API",
        "version": settings.APP_VERSION,
        "docs": "/docs",
        "endpoints": {
            "generate_text": "POST /api/v1/generate",
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