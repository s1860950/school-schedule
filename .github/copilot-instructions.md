# AI Agent Instructions for FastAPI AI Backend

## Project Overview
This is a **FastAPI-based AI text generation backend** supporting multiple AI providers (Hugging Face, OpenAI, DeepSeek). It exposes REST endpoints for AI-powered text generation with provider selection and configurable generation parameters.

## Architecture & Key Components

### Directory Structure
- **`app/core/`** - Application configuration management
  - `config.py`: Settings loaded from environment variables (API keys, model names, timeouts)
- **`app/api/endpoints/`** - REST API handlers
  - `ai.py`: HTTP endpoints for text generation and provider information
- **`app/schemas/`** - Pydantic models for request/response validation
  - `ai.py`: `GenerationRequest` (input), `GenerationResponse` (output), `AIProvider` enum
- **`app/services/`** - Core business logic
  - `ai_service.py`: `AIService` class with provider-specific implementations
- **`app/main.py`** - FastAPI app initialization with CORS middleware

### Data Flow: Request → Response
```
POST /api/v1/generate
  ↓ (GenerationRequest validated by Pydantic)
APIRouter @ app/api/endpoints/ai.py::generate_text()
  ↓ (calls await ai_service.generate_text(request_data))
AIService @ app/services/ai_service.py
  ├─ Determines provider from request
  ├─ Calls provider-specific method (generate_text_huggingface/openai/deepseek)
  └─ Returns dict with {success, generated_text, provider, tokens_used, error}
  ↓ (wrapped in GenerationResponse)
HTTP 200/500 with JSON response
```

## Critical Patterns & Conventions

### 1. **Async/Await Everywhere**
All I/O operations use `async`/`await`. Every provider method returns a coroutine:
```python
async def generate_text(self, request_data: Dict[str, Any]) -> Dict[str, Any]:  # Returns awaitable
    result = await self.generate_text_huggingface(...)  # Await provider calls
```
When adding new features: use `async def`, use `await` for all external API calls, and use `httpx.AsyncClient` for HTTP.

### 2. **Provider Pattern with Fallback**
Each AI provider has a dedicated method:
- `generate_text_huggingface()` - Hugging Face Inference API (free models)
- `generate_text_openai()` - OpenAI-compatible APIs (OpenRouter, LocalAI)
- `generate_text_deepseek()` - DeepSeek API

The main `generate_text()` method routes to appropriate provider based on `provider` parameter. Default provider is `settings.AI_PROVIDER` (configured via `AI_PROVIDER` env var, defaults to "mock").

### 3. **Configuration as Environment Variables**
All settings in `app/core/config.py` read from `.env`:
```python
HUGGINGFACE_API_KEY=hf_xxx
OPENAI_API_KEY=sk_xxx
DEEPSEEK_API_KEY=...
AI_PROVIDER=huggingface  # Default provider
```
No hardcoded secrets or magic values. Settings object is singleton: `from app.core.config import settings`.

### 4. **Request/Response Validation with Pydantic**
All API inputs/outputs are validated:
- `GenerationRequest`: min_length=1, max_length=2000 for prompt; temperature 0.1-1.0; max_tokens 1-2000
- `GenerationResponse`: success boolean + conditional fields (generated_text OR error)

Always use Pydantic models for API contracts. Validation happens before your code runs.

### 5. **Error Handling for External APIs**
Provider methods follow this pattern:
```python
try:
    async with httpx.AsyncClient(timeout=self.timeout) as client:
        response = await client.post(...)
        if response.status_code == 200:
            return {...}
    logger.error(f"API error: {response.status_code}")
except Exception as e:
    logger.error(f"Request failed: {str(e)}")
return {"text": "", "model": "..."}  # Graceful degradation
```
Always log errors; return dict with empty text on failure. Endpoint converts failure responses to HTTP 500 with error message.

### 6. **Request/Response Structure**
All provider methods return dict with:
- `"text"` - Generated text (string, can be empty)
- `"model"` - Model name used (string)
- `"tokens"` (optional) - Token count if API provides it (int)

Main service wraps this as `GenerationResponse` schema.

## Running & Development

### Start Server
```bash
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
# Or: python app/main.py (uses settings.PORT and settings.DEBUG)
```

### Access API
- Interactive docs: `http://localhost:8000/docs` (Swagger UI)
- ReDoc: `http://localhost:8000/redoc`
- Health check: `GET /health`
- Generate text: `POST /api/v1/generate` with `GenerationRequest` payload
- List providers: `GET /api/v1/providers`

### Dependencies
Package `requirements.txt` pins versions (includes comment about Pydantic being old version without Rust):
- fastapi, uvicorn (web framework)
- pydantic (request validation)
- httpx (async HTTP client)
- python-dotenv (env var loading)
- aiohttp (dependency for some libs)

## When You Add Features

1. **New Provider**: Create `async def generate_text_<provider>()` in `AIService`, handle auth/headers/payload formatting, route it in `generate_text()`'s if/elif chain. Add provider description to `GET /api/v1/providers` endpoint.

2. **New Endpoint**: Add route to `app/api/endpoints/ai.py`, create corresponding Pydantic schema in `app/schemas/ai.py`, call service method, return response.

3. **Configuration**: Add to `app/core/config.py` Settings class with `os.getenv()` fallback, use in service/endpoint.

4. **Middleware/Global Behavior**: Modify `app.main.py` (CORS is already there as example).

## External Integrations
- **Hugging Face Inference API** - Free models, requires HF token, uses prompt template `<s>[INST] {system} \n\n {user} [/INST]`
- **OpenAI-compatible APIs** - Supports chat completions format (system/user messages), custom base URL via config
- **DeepSeek API** - Similar chat format with stream=False parameter

All APIs require authentication via Bearer token in Authorization header.
