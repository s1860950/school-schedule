import logging
from enum import Enum
from typing import Any, Dict
from urllib.parse import parse_qs

from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from app.core.config import settings
from app.schemas.ai import AIProvider, MAX_OUTPUT_TOKENS, PROMPT_MAX_LENGTH, GenerationRequest, GenerationResponse
from app.services.ai_service import ai_service
from app.services.schedule_utils import create_schedule_excel
from fastapi.responses import StreamingResponse

router = APIRouter()
logger = logging.getLogger(__name__)

_GENERATION_REQUEST_SCHEMA = {
    "type": "object",
    "required": ["prompt"],
    "properties": {
        "prompt": {
            "type": "string",
            "minLength": 1,
            "maxLength": PROMPT_MAX_LENGTH,
            "description": "Prompt text to generate a response for",
        },
        "system_prompt": {
            "type": "string",
            "description": "Optional system prompt",
            "default": "You are a helpful AI assistant. Reply in Russian.",
        },
        "max_tokens": {
            "type": "integer",
            "minimum": 1,
            "maximum": MAX_OUTPUT_TOKENS,
            "default": MAX_OUTPUT_TOKENS,
        },
        "temperature": {
            "type": "number",
            "minimum": 0.1,
            "maximum": 1.0,
            "default": 0.7,
        },
        "provider": {
            "type": "string",
            "enum": [provider.value for provider in AIProvider],
            "default": AIProvider.YANDEXGPT.value,
        },
    },
}

_GENERATION_REQUEST_EXAMPLE = {
    "prompt": "Составь реалистичное, полное и логически выверенное недельное расписание для начальной школы: 1, 2, 3 и 4 класс, на Понедельник–Пятницу. Главный обязательный итог ответа — ОДНА ЕДИНАЯ БОЛЬШАЯ ИТОГОВАЯ ТАБЛИЦА РАСПИСАНИЯ ДЛЯ ВСЕХ КЛАССОВ СРАЗУ, где по строкам идут дни и временные слоты, а по столбцам — 1, 2, 3 и 4 класс, чтобы в одной таблице сразу было видно всё расписание всей школы. Все промежуточные расчёты, проверки и вспомогательные таблицы допустимы только как подготовка, но основным результатом обязательно должна быть именно эта единая общая таблица расписания. Работай строго по приоритетам: сначала полностью выполни обязательные требования 1-го и 2-го уровня, и только потом мягко улучшай по 3-му уровню, не нарушая более важные ограничения. Если улучшение конфликтует хотя бы с одним обязательным правилом, всегда сохраняй обязательное правило. ОБЯЗАТЕЛЬНЫЕ ТРЕБОВАНИЯ 1-ГО УРОВНЯ: 1) Нагрузка: 1 класс — 4–5 уроков в день; 2 класс — 4–5; 3 класс — 4–6; 4 класс — 4–6. 2) Используй только слоты: 8:30–9:15, 9:30–10:15, 10:30–11:15, 11:30–12:15, 12:30–13:15, 13:30–14:15. 3) Если у класса 4 урока — только первые 4 слота подряд; если 5 — первые 5; если 6 — все 6; внутри дня нельзя делать окна; если в конце дня слоты не используются, ставь «—». 4) Используй только предметы: Математика, Русский язык, Литературное чтение, Окружающий мир, ИЗО, Музыка, Труд / Технология, Физкультура. 5) В один день у одного класса нельзя повторять: Музыку, ИЗО, Труд / Технологию, Физкультуру, Окружающий мир. 6) Повторять можно только Математику, Русский язык и Литературное чтение, не более 2 раз в день каждый. 7) Ресурсные предметы распределяй ПЕРВЫМИ как отдельную общешкольную сетку ограниченных ресурсов: Музыка, ИЗО, Труд / Технология, Физкультура. Сначала обязательно построй для всей школы общую сетку этих предметов по всем дням и слотам, и только потом заполняй остальные уроки. Разные ресурсные предметы могут идти одновременно у разных классов в одном и том же слоте, если это разные предметы. Запрещено только одновременное совпадение одного и того же ресурсного предмета у нескольких классов в одном и том же дне и слоте. То есть в каждом конкретном слоте по всей школе может быть не более одной Музыки, не более одного ИЗО, не более одного Труда / Технологии и не более одной Физкультуры. Для Математики, Русского языка, Литературного чтения и Окружающего мира совпадения между классами разрешены. ОБЯЗАТЕЛЬНЫЕ ТРЕБОВАНИЯ 2-ГО УРОВНЯ: недельная частота предметов обязательна и должна быть частью построения и проверки. Для каждого класса сначала посчитай общее число недельных слотов, затем заранее распредели недельную частоту предметов, и только потом размещай их по дням и слотам. Для каждого класса обязательно соблюдай: Математика — 4–5 раз в неделю, Русский язык — 4–5, Литературное чтение — 3–4, Физкультура — 2–3. Также старайся максимально точно соблюсти: Окружающий мир — 1–2, Музыка — 1, ИЗО — 1, Труд / Технология — 1. Допускается отклонение не более чем на 1 только в исключительном случае, если без этого невозможно соблюсти требования 1-го уровня. Если отклонение произошло, оно должно быть явно отмечено в самопроверке как вынужденное исключение. Нельзя допускать заметный недобор или перебор основных предметов. ДОПОЛНИТЕЛЬНЫЕ ТРЕБОВАНИЯ 3-ГО УРОВНЯ: 1) 1 класс должен быть легче, чем 3–4 классы; 2) пятница желательно легче; 3) основные предметы должны встречаться чаще, чем творческие и практические; 4) распределение уроков должно быть реалистичным, разнообразным и не шаблонным; не ставь все основные предметы только в начало дня, а все творческие и практические только в конец; Физкультура, Музыка, ИЗО и Труд / Технология могут стоять в начале, середине и конце дня; особенно не концентрируй Физкультуру только на последних уроках; 5) не делай одинаковый порядок уроков у всех классов; 6) не делай одинаковый первый урок у всех классов почти каждый день; 7) не делай повторяющийся шаблон типа «Математика → Русский язык → Литературное чтение → Окружающий мир» почти каждый день; 8) не делай все дни недели слишком похожими; 9) не делай механическое расписание. ОБЯЗАТЕЛЬНЫЙ ПОРЯДОК ПОСТРОЕНИЯ: ШАГ 1 — определи количество уроков по каждому дню для каждого класса так, чтобы соблюдалась допустимая нагрузка и получалось нужное число недельных слотов. ШАГ 2 — заранее распредели недельную частоту всех предметов по каждому классу. ШАГ 3 — ПЕРВЫМ ОБЯЗАТЕЛЬНЫМ действием построй для всей школы общую сетку ресурсных предметов (Музыка, ИЗО, Труд / Технология, Физкультура) по всем дням и слотам с проверкой отсутствия запрещённых совпадений. ШАГ 4 — только после этого заполни оставшиеся слоты остальными предметами. ШАГ 5 — проведи полную самопроверку. ФОРМАТ ОТВЕТА: 1) обязательно выведи ОДНУ ГЛАВНУЮ ИТОГОВУЮ ТАБЛИЦУ РАСПИСАНИЯ ДЛЯ ВСЕХ КЛАССОВ СРАЗУ; 2) после неё дай краткую самопроверку по всем ограничениям.",
    "system_prompt": "You are a helpful AI assistant. Reply in Russian.",
    # "max_tokens": 300,
    "temperature": 0.1,
    "provider": AIProvider.YANDEXGPT.value,
}


def _normalize_generation_payload(raw_data: Dict[str, Any]) -> Dict[str, Any]:
    normalized = dict(raw_data)

    for field_name in ("system_prompt", "provider"):
        if normalized.get(field_name) in ("", None):
            normalized.pop(field_name, None)

    if normalized.get("max_tokens") not in ("", None):
        try:
            normalized["max_tokens"] = int(normalized["max_tokens"])
        except (TypeError, ValueError):
            pass

    if normalized.get("temperature") not in ("", None):
        try:
            normalized["temperature"] = float(normalized["temperature"])
        except (TypeError, ValueError):
            pass

    return normalized


async def _parse_generation_request(http_request: Request) -> GenerationRequest:
    content_type = (http_request.headers.get("content-type") or "").split(";", 1)[0].strip().lower()

    if content_type in ("", "application/json"):
        raw_body = await http_request.body()
        if not raw_body:
            payload: Any = {}
        else:
            try:
                payload = await http_request.json()
            except Exception as exc:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid JSON body. Send an object like {\"prompt\": \"...\"}.",
                ) from exc
    elif content_type == "application/x-www-form-urlencoded":
        form_payload = parse_qs((await http_request.body()).decode("utf-8"), keep_blank_values=True)
        payload = {
            key: values[-1] if isinstance(values, list) and values else values
            for key, values in form_payload.items()
        }
    elif content_type == "multipart/form-data":
        try:
            payload = dict(await http_request.form())
        except AssertionError as exc:
            raise HTTPException(
                status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                detail=(
                    "multipart/form-data requires the optional 'python-multipart' package. "
                    "Use application/json, text/plain, or application/x-www-form-urlencoded instead."
                ),
            ) from exc
    elif content_type == "text/plain":
        payload = {"prompt": (await http_request.body()).decode("utf-8").strip()}
    else:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=(
                "Unsupported media type. Use application/json, text/plain, "
                "application/x-www-form-urlencoded, or multipart/form-data."
            ),
        )

    if isinstance(payload, str):
        payload = {"prompt": payload}
    elif payload is None:
        payload = {}
    elif not isinstance(payload, dict):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Request body must be a JSON object or a plain-text prompt.",
        )

    normalized_payload = _normalize_generation_payload(payload)

    try:
        return GenerationRequest(**normalized_payload)
    except ValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=exc.errors(),
        ) from exc


def _resolve_generation_error_status(error_message: str) -> int:
    message = (error_message or "").lower()
    if message.startswith("401:") or 'httpcode":401' in message or "unauthorized" in message:
        return status.HTTP_401_UNAUTHORIZED
    if message.startswith("403:") or 'httpcode":403' in message or "forbidden" in message or "permission" in message:
        return status.HTTP_403_FORBIDDEN
    if message.startswith("404:") or 'httpcode":404' in message or "not found" in message:
        return status.HTTP_404_NOT_FOUND
    if message.startswith("429:") or 'httpcode":429' in message or "rate limit" in message or "too many requests" in message:
        return status.HTTP_429_TOO_MANY_REQUESTS

    bad_request_markers = (
        "not configured",
        "required",
        "invalid",
        "missing",
        "unavailable for this account",
    )
    if any(marker in message for marker in bad_request_markers):
        return status.HTTP_400_BAD_REQUEST
    return status.HTTP_500_INTERNAL_SERVER_ERROR


@router.post(
    "/generate",
    response_model=GenerationResponse,
    summary="Generate text with AI",
    description="Accepts JSON, text/plain, or form-data and returns generated text from the selected AI provider.",
    openapi_extra={
        "requestBody": {
            "required": True,
            "content": {
                "application/json": {
                    "schema": _GENERATION_REQUEST_SCHEMA,
                    "example": _GENERATION_REQUEST_EXAMPLE,
                },
                "text/plain": {
                    "schema": {"type": "string"},
                    "example": "Explain how this API works",
                },
                "application/x-www-form-urlencoded": {
                    "schema": _GENERATION_REQUEST_SCHEMA,
                },
                "multipart/form-data": {
                    "schema": _GENERATION_REQUEST_SCHEMA,
                },
            },
        }
    },
)
async def generate_text(request: Request):
    """
    Generate text through one of the configured AI providers.

    Supported request formats:
    - JSON object matching GenerationRequest
    - text/plain where the whole body is treated as prompt
    - form-data or urlencoded fields matching GenerationRequest
    """
    try:
        parsed_request = await _parse_generation_request(request)
        logger.info("Generating text with provider: %s", parsed_request.provider)

        request_data = parsed_request.dict()

        try:
            provider = request_data.get("provider")
            if isinstance(provider, Enum):
                request_data["provider"] = provider.value
        except Exception:
            pass

        result = await ai_service.generate_text(request_data)

        if not result.get("success"):
            logger.error("AI generation failed: %s", result)
            error_message = result.get("error", "AI generation failed")
            raise HTTPException(
                status_code=_resolve_generation_error_status(error_message),
                detail=error_message,
            )

        if settings.DEBUG:
            return JSONResponse(content=result, status_code=200)

        try:
            return GenerationResponse(**result)
        except Exception as exc:
            logger.exception("Failed to build GenerationResponse; result=%s", result)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Response build error: {exc}",
            ) from exc

    except ValueError as exc:
        logger.warning("Bad request: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except HTTPException:
        raise
    except Exception:
        logger.exception("Unexpected error while generating text")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.get("/providers")
async def get_available_providers():
    return {
        "providers": [
            {
                "id": "huggingface",
                "name": "Hugging Face",
                "description": "Free models via the Inference API",
                "needs_key": True,
            },
            {
                "id": "openai",
                "name": "OpenAI Compatible",
                "description": "OpenAI-compatible APIs such as OpenRouter or LocalAI",
                "needs_key": True,
            },
            {
                "id": "deepseek",
                "name": "DeepSeek",
                "description": "DeepSeek API",
                "needs_key": True,
            },
            {
                "id": "yandexgpt",
                "name": "YandexGPT",
                "description": "Yandex Cloud Foundation Models / OpenAI-compatible API",
                "needs_key": True,
            },
            {
                "id": "gigachat",
                "name": "Giga Chat",
                "description": "Giga Chat (OpenAI-compatible)",
                "needs_key": True,
            },
        ]
    }


@router.post("/generate-excel")
async def generate_excel(request: Request):
    """
    Генерирует Excel файл из текста расписания
    """
    try:
        body = await request.json()
        schedule_text = body.get("schedule_text", "")
        
        if not schedule_text:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="schedule_text is required"
            )
        
        # Создаём Excel файл
        excel_file = create_schedule_excel(schedule_text)
        
        return StreamingResponse(
            iter([excel_file.getvalue()]),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": "attachment; filename=schedule.xlsx"}
        )
    
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Error generating Excel file")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error generating Excel file: {str(exc)}"
        )
