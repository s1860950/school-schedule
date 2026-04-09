import httpx
import asyncio
import time
import uuid
from typing import Dict, Any, Optional, List, Tuple
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)

# Optional official SDK import (preferred if installed)
try:
    from gigachat import GigaChat as _GigaChat  # type: ignore
except Exception:
    _GigaChat = None

class AIService:
    def __init__(self):
        self.timeout = httpx.Timeout(settings.REQUEST_TIMEOUT)
        # Giga Chat token cache
        self._giga_token: Optional[str] = None
        self._giga_token_expires: float = 0.0

    def _giga_api_base(self) -> str:
        base = settings.GIGA_API_BASE.rstrip("/")
        if not base.endswith("/api/v1"):
            base = f"{base}/api/v1"
        return base

    def _giga_root_base(self) -> str:
        base = settings.GIGA_API_BASE.rstrip("/")
        if base.endswith("/api/v1"):
            return base[:-7]
        return base

    def _giga_model(self) -> str:
        model = (settings.GIGA_MODEL or "").strip()
        if not model or model.lower() == "gigachat-default":
            return "GigaChat"
        return model

    def _yandex_api_base(self) -> str:
        base = settings.YANDEX_API_BASE.rstrip("/")
        if base.endswith("/foundationModels/v1"):
            return f"{base[:-20]}/v1"
        if not base.endswith("/v1"):
            base = f"{base}/v1"
        return base

    def _yandex_completion_url(self) -> str:
        base = settings.YANDEX_API_BASE.rstrip("/")
        if base.endswith("/foundationModels/v1"):
            return f"{base}/completion"
        if base.endswith("/v1"):
            base = base[:-3]
        return f"{base}/foundationModels/v1/completion"

    def _yandex_model_uri(self) -> str:
        model = (settings.YANDEX_MODEL or "").strip()
        if not model:
            raise ValueError("YandexGPT model not configured")
        if model.startswith("gpt://"):
            return model

        folder_id = (settings.YANDEX_FOLDER_ID or "").strip()
        if not folder_id:
            raise ValueError("YANDEX_FOLDER_ID is required when YANDEX_MODEL is not a full gpt:// URI")
        return f"gpt://{folder_id}/{model}"

    def _yandex_auth_candidates(self) -> List[Tuple[str, str]]:
        candidates: List[Tuple[str, str]] = []
        iam_token = (settings.YANDEX_IAM_TOKEN or "").strip()
        api_key = (settings.YANDEX_API_KEY or "").strip()

        if iam_token:
            candidates.append(("Bearer", iam_token))
        if api_key:
            candidates.append(("Api-Key", api_key))

        if not candidates:
            raise ValueError("YandexGPT credentials not configured (YANDEX_API_KEY or YANDEX_IAM_TOKEN required)")

        unique_candidates: List[Tuple[str, str]] = []
        seen = set()
        for scheme, token in candidates:
            key = (scheme, token)
            if key in seen:
                continue
            seen.add(key)
            unique_candidates.append((scheme, token))
        return unique_candidates

    @staticmethod
    def _extract_message_content(content: Any) -> str:
        if isinstance(content, str):
            return content
        if isinstance(content, dict):
            return str(content.get("text") or "")
        if isinstance(content, list):
            parts = []
            for item in content:
                if isinstance(item, str):
                    parts.append(item)
                elif isinstance(item, dict):
                    text = item.get("text")
                    if text:
                        parts.append(str(text))
            return "".join(parts)
        return ""

    @staticmethod
    def _safe_int(value: Any) -> Optional[int]:
        if value is None:
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    def _extract_usage_details(self, usage: Dict[str, Any]) -> Dict[str, Any]:
        if not isinstance(usage, dict):
            return {}

        prompt_tokens = self._safe_int(
            usage.get("prompt_tokens") or usage.get("promptTokens") or usage.get("inputTextTokens")
        )
        completion_tokens = self._safe_int(
            usage.get("completion_tokens") or usage.get("completionTokens") or usage.get("completionTokensCount")
        )

        completion_details = usage.get("completionTokensDetails") or {}
        reasoning_tokens = self._safe_int(
            completion_details.get("reasoningTokens") if isinstance(completion_details, dict) else None
        )

        total_tokens = self._safe_int(usage.get("total_tokens") or usage.get("totalTokens"))
        if total_tokens is None and prompt_tokens is not None and completion_tokens is not None:
            total_tokens = prompt_tokens + completion_tokens

        details: Dict[str, Any] = {}
        if total_tokens is not None:
            details["tokens"] = total_tokens
        if prompt_tokens is not None:
            details["prompt_tokens"] = prompt_tokens
        if completion_tokens is not None:
            details["completion_tokens"] = completion_tokens
        if reasoning_tokens is not None:
            details["reasoning_tokens"] = reasoning_tokens
        return details
        
    async def generate_text_huggingface(self, prompt: str, system_prompt: str, max_tokens: int, temperature: float) -> Dict[str, Any]:
        """Генерация текста через Hugging Face Inference API"""
        if not settings.HUGGINGFACE_API_KEY:
            raise ValueError("Hugging Face API key not configured")
        
        headers = {
            "Authorization": f"Bearer {settings.HUGGINGFACE_API_KEY}",
            "Content-Type": "application/json"
        }
        
        # Формируем полный промпт
        full_prompt = f"<s>[INST] {system_prompt}\n\n{prompt} [/INST]"
        
        payload = {
            "inputs": full_prompt,
            "parameters": {
                "max_new_tokens": max_tokens,
                "temperature": temperature,
                "return_full_text": False
            }
        }
        
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"https://api-inference.huggingface.co/models/{settings.HUGGINGFACE_MODEL}",
                    headers=headers,
                    json=payload
                )
                
                if response.status_code == 200:
                    result = response.json()
                    if isinstance(result, list) and len(result) > 0:
                        return {
                            "text": result[0].get("generated_text", ""),
                            "model": settings.HUGGINGFACE_MODEL
                        }
                else:
                    logger.error(f"Hugging Face API error: {response.status_code} - {response.text}")
                    
        except Exception as e:
            logger.error(f"Hugging Face request failed: {str(e)}")
        
        return {"text": "", "model": settings.HUGGINGFACE_MODEL}
    
    async def generate_text_openai(self, prompt: str, system_prompt: str, max_tokens: int, temperature: float) -> Dict[str, Any]:
        """Генерация текста через OpenAI-совместимое API"""
        if not settings.OPENAI_API_KEY:
            raise ValueError("OpenAI API key not configured")
        
        headers = {
            "Authorization": f"Bearer {settings.OPENAI_API_KEY}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": settings.OPENAI_MODEL,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ],
            "max_tokens": max_tokens,
            "temperature": temperature
        }
        
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{settings.OPENAI_API_BASE}/chat/completions",
                    headers=headers,
                    json=payload
                )
                
                if response.status_code == 200:
                    data = response.json()
                    usage_details = self._extract_usage_details(data.get("usage", {}))
                    first_choice = data.get("choices", [{}])[0] if isinstance(data.get("choices"), list) else {}
                    return {
                        "text": data["choices"][0]["message"]["content"],
                        "model": data["model"],
                        "finish_reason": first_choice.get("finish_reason"),
                        **usage_details,
                    }
                else:
                    logger.error(f"OpenAI API error: {response.status_code} - {response.text}")
                    
        except Exception as e:
            logger.error(f"OpenAI request failed: {str(e)}")
        
        return {"text": "", "model": settings.OPENAI_MODEL}
    
    async def generate_text_deepseek(self, prompt: str, system_prompt: str, max_tokens: int, temperature: float) -> Dict[str, Any]:
        """Генерация текста через DeepSeek API"""
        if not settings.DEEPSEEK_API_KEY:
            raise ValueError("DeepSeek API key not configured")
        
        headers = {
            "Authorization": f"Bearer {settings.DEEPSEEK_API_KEY}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": settings.DEEPSEEK_MODEL,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ],
            "max_tokens": max_tokens,
            "temperature": temperature,
            "stream": False
        }
        
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{settings.DEEPSEEK_API_BASE}/chat/completions",
                    headers=headers,
                    json=payload
                )
                
                if response.status_code == 200:
                    data = response.json()
                    usage_details = self._extract_usage_details(data.get("usage", {}))
                    first_choice = data.get("choices", [{}])[0] if isinstance(data.get("choices"), list) else {}
                    return {
                        "text": data["choices"][0]["message"]["content"],
                        "model": data["model"],
                        "finish_reason": first_choice.get("finish_reason"),
                        **usage_details,
                    }
                else:
                    logger.error(f"DeepSeek API error: {response.status_code} - {response.text}")
                    
        except Exception as e:
            logger.error(f"DeepSeek request failed: {str(e)}")
        
        return {"text": "", "model": settings.DEEPSEEK_MODEL}

    async def generate_text_yandexgpt(self, prompt: str, system_prompt: str, max_tokens: int, temperature: float) -> Dict[str, Any]:
        """Генерация текста через YandexGPT API."""
        model_uri = self._yandex_model_uri()
        folder_id = (settings.YANDEX_FOLDER_ID or "").strip()
        completion_url = self._yandex_completion_url()

        completion_payload = {
            "modelUri": model_uri,
            "completionOptions": {
                "stream": False,
                "temperature": temperature,
                "maxTokens": str(max_tokens)
            },
            "messages": [
                {"role": "system", "text": system_prompt},
                {"role": "user", "text": prompt}
            ]
        }

        last_error = None
        for scheme, token in self._yandex_auth_candidates():
            headers = {
                "Authorization": f"{scheme} {token}",
                "Content-Type": "application/json",
                "Accept": "application/json"
            }
            if folder_id:
                headers["x-folder-id"] = folder_id

            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    response = await client.post(completion_url, headers=headers, json=completion_payload)
                    if response.status_code == 200:
                        data = response.json()
                        result = data.get("result", data)
                        alternatives = result.get("alternatives") or data.get("alternatives") or []
                        first_alternative = alternatives[0] if alternatives else {}
                        message = first_alternative.get("message", {})
                        text = message.get("text") or first_alternative.get("text") or ""
                        alternative_status = first_alternative.get("status")
                        usage = result.get("usage", {}) or data.get("usage", {})
                        usage_details = self._extract_usage_details(usage)

                        return {
                            "text": text,
                            "model": result.get("modelVersion", model_uri),
                            "alternative_status": alternative_status,
                            "truncated": alternative_status == "ALTERNATIVE_STATUS_TRUNCATED_FINAL",
                            **usage_details,
                        }

                    last_error = f"{response.status_code}: {response.text}"
                    logger.debug("YandexGPT completion failed with %s", last_error)

            except Exception as e:
                last_error = str(e)
                logger.debug("YandexGPT request failed: %s", e)

        if last_error:
            logger.error("YandexGPT request failed, last error: %s", last_error)
            raise ValueError(last_error)

        return {"text": "", "model": model_uri}

    async def generate_text_gigachat(self, prompt: str, system_prompt: str, max_tokens: int, temperature: float) -> Dict[str, Any]:
        """Генерация текста через Giga Chat API (OpenAI-совместимый интерфейс)"""
        # Obtain a valid access token (exchanges Basic->Access token if needed)
        token = await self._get_giga_access_token()

        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }

        api_base = self._giga_api_base()
        root_base = self._giga_root_base()
        giga_model = self._giga_model()

        # Prefer the official OpenAI-compatible v1 route first.
        endpoint_candidates = [
            f"{api_base}/chat/completions",
            f"{api_base}/assistant/generate",
            f"{root_base}/api/rest/v1/assistant/generate",
        ]

        last_error = None
        for url in endpoint_candidates:
            # Payload shape: prefer Sber assistant shape for assistant endpoints, otherwise OpenAI chat
            if url.endswith("assistant/generate"):
                payload = {
                    "model": giga_model,
                    "input": {
                        "text": prompt,
                        "system": system_prompt
                    },
                    "max_tokens": max_tokens,
                    "temperature": temperature
                }
            else:
                payload = {
                    "model": giga_model,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": prompt}
                    ],
                    "max_tokens": max_tokens,
                    "temperature": temperature,
                    "stream": False
                }

            try:
                # Prefer explicit CA bundle when provided; otherwise use default verification behavior
                verify_value = settings.GIGA_CA_BUNDLE if getattr(settings, "GIGA_CA_BUNDLE", None) else None
                async with httpx.AsyncClient(timeout=self.timeout, verify=verify_value) as client:
                    # Respect configured retry attempts
                    for attempt in range(max(1, settings.MAX_RETRIES)):
                        try:
                            resp = await client.post(url, headers=headers, json=payload)
                        except Exception as e:
                            last_error = str(e)
                            logger.debug("Giga request exception to %s: %s", url, e)
                            continue

                        if resp.status_code in (200, 201):
                            try:
                                data = resp.json()
                            except Exception:
                                data = {}

                            # Try to extract text for both assistant-style and OpenAI-style responses
                            text = ""
                            if isinstance(data, dict):
                                # OpenAI-style
                                try:
                                    text = data["choices"][0]["message"]["content"]
                                except Exception:
                                    pass

                                # Sber assistant-style: might be at data['result'] or data['response']
                                if not text:
                                    for key in ("result", "response", "answer"):
                                        candidate = data.get(key)
                                        if isinstance(candidate, dict):
                                            text = candidate.get("text") or candidate.get("output") or ""
                                            if text:
                                                break
                                        if isinstance(candidate, str) and candidate:
                                            text = candidate
                                            break

                            if text:
                                usage_details = self._extract_usage_details(data.get("usage", {}))
                                first_choice = data.get("choices", [{}])[0] if isinstance(data.get("choices"), list) else {}
                                return {
                                    "text": text,
                                    "model": data.get("model", giga_model),
                                    "finish_reason": first_choice.get("finish_reason"),
                                    **usage_details,
                                }

                        # non-success — log and try next attempt / endpoint
                        last_error = f"{resp.status_code}: {resp.text}"
                        logger.debug("Giga endpoint %s returned %s", url, last_error)
                        if resp.status_code == 404 and "No such model" in resp.text:
                            raise ValueError(f"GigaChat model '{giga_model}' is unavailable for this account")

            except ValueError:
                raise
            except Exception as e:
                last_error = str(e)
                logger.debug("Giga endpoint %s request failed: %s", url, e)

        if last_error:
            logger.error("Giga Chat failed for all endpoints, last error: %s", last_error)
            raise ValueError(last_error)
        return {"text": "", "model": giga_model}

    async def _get_giga_access_token(self) -> str:
        """Return a valid Giga Chat access token.

        If `GIGA_AUTH_KEY` is provided, exchange it for a short-lived Access token via /api/v2/oauth.
        Otherwise, if `GIGA_API_KEY` is set, treat it as an Access token (caller is responsible for expiry).
        """
        now = time.time()

        # If we have a cached token that's still valid, return it
        if self._giga_token and now < self._giga_token_expires - 5:
            return self._giga_token

        # If an Authorization key is configured, request a new access token
        if settings.GIGA_AUTH_KEY:
            # Prefer SDK if available — run in thread to avoid blocking event loop
            if _GigaChat is not None:
                try:
                    def _sdk_get_token():
                        # Pass `ca_bundle_file` to SDK if configured so SDK can validate server certs
                        sdk_kwargs = {}
                        if getattr(settings, "GIGA_CA_BUNDLE", None):
                            sdk_kwargs["ca_bundle_file"] = settings.GIGA_CA_BUNDLE
                        g = _GigaChat(credentials=settings.GIGA_AUTH_KEY, **sdk_kwargs)
                        if hasattr(g, "get_token"):
                            return g.get_token()
                        if hasattr(g, "getToken"):
                            return g.getToken()
                        return None

                    sdk_resp = await asyncio.to_thread(_sdk_get_token)
                    if sdk_resp:
                        # sdk_resp might be dict-like or object
                        if isinstance(sdk_resp, dict):
                            access_token = sdk_resp.get("access_token") or sdk_resp.get("token") or sdk_resp.get("accessToken")
                            expires_in = int(sdk_resp.get("expires_at") or sdk_resp.get("expires_in") or 1800)
                        else:
                            access_token = getattr(sdk_resp, "access_token", None) or getattr(sdk_resp, "token", None)
                            expires_in = int(getattr(sdk_resp, "expires_at", 0) or getattr(sdk_resp, "expires_in", 1800) or 1800)

                        if access_token:
                            self._giga_token = access_token
                            # If expires_at is an absolute timestamp, calculate remaining
                            if expires_in and expires_in > 1_000_000_000:
                                self._giga_token_expires = expires_in
                            else:
                                self._giga_token_expires = time.time() + expires_in
                            logger.info("Obtained Giga Chat token via SDK, expires in %s seconds", expires_in)
                            return self._giga_token
                except Exception as e:
                    logger.debug("Giga SDK token request failed: %s", e)
                    # fall through to httpx-based attempts

            oauth_paths = ["/api/v2/oauth", "/api/v1/oauth/token", "/api/v1/oauth", "/oauth/token"]
            headers = {
                "Authorization": f"Basic {settings.GIGA_AUTH_KEY}",
                "Content-Type": "application/x-www-form-urlencoded",
                "Accept": "application/json",
                "RqUID": str(uuid.uuid4()),
                "User-Agent": "GigaChat-python-lib",
            }
            data = {"scope": "GIGACHAT_API_PERS"}

            last_error = None
            oauth_candidates = [settings.GIGA_AUTH_URL.rstrip("/")]
            root_base = self._giga_root_base()
            oauth_candidates.extend(f"{root_base}{path}" for path in oauth_paths)

            for url in oauth_candidates:
                try:
                    verify_value = settings.GIGA_CA_BUNDLE if getattr(settings, "GIGA_CA_BUNDLE", None) else None
                    async with httpx.AsyncClient(timeout=self.timeout, verify=verify_value) as client:
                        resp = await client.post(url, headers=headers, data=data)
                except Exception as e:
                    last_error = str(e)
                    logger.debug("Giga OAuth request to %s failed: %s", url, e)
                    continue

                if resp.status_code in (200, 201):
                    try:
                        d = resp.json()
                    except Exception:
                        d = {}

                    access_token = d.get("access_token") or d.get("token") or d.get("accessToken")
                    expires_in = int(d.get("expires_in", 1800)) if d.get("expires_in") else 1800
                    if not access_token:
                        last_error = resp.text
                        logger.error("Giga OAuth response missing token at %s: %s", url, resp.text)
                        continue

                    # Cache token with a small safety margin
                    self._giga_token = access_token
                    self._giga_token_expires = time.time() + expires_in
                    logger.info("Obtained new Giga Chat access token, expires in %s seconds", expires_in)
                    return self._giga_token

                last_error = f"{resp.status_code}: {resp.text}"
                logger.debug("Giga OAuth non-200 at %s: %s", url, last_error)

            logger.error("Giga OAuth failed for all endpoints, last error: %s", last_error)
            raise ValueError("Failed to obtain Giga Chat access token")

        # Fallback: use GIGA_API_KEY if present (assumed to be an access token)
        if settings.GIGA_API_KEY:
            logger.info("Using fallback GIGA_API_KEY from config (may be short-lived)")
            return settings.GIGA_API_KEY

        raise ValueError("Giga Chat credentials not configured (GIGA_AUTH_KEY or GIGA_API_KEY required)")
    
    async def generate_text(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """Основной метод генерации текста"""
        provider = request_data.get("provider", settings.AI_PROVIDER)
        prompt = request_data.get("prompt", "Сгенерируй расписание на неделю для начальных классов (всего 1-4 - 4 класса), на 5 дней в неделю. Предметы - изо, труд, физкультура, музыка - не должны накладываться друг на друга. У 1го класса максимум 5 уроков, у других - 6. У каждого класса свой классный руководитель. Предметы не доложны повторяться в один день для одного класса. Расписание должно быть в виде таблицы с указанием времени, предмета и классного руководителя. Время уроков: 8:30-9:15, 9:30-10:15, 10:30-11:15, 11:30-12:15, 13:00-13:45, 14:00-14:45.")
        system_prompt = request_data.get("system_prompt", "Ты - полезный AI ассистент.")
        max_tokens = request_data.get("max_tokens", 700)
        temperature = request_data.get("temperature", 0.7)
        
        try:
            if provider == "huggingface":
                result = await self.generate_text_huggingface(prompt, system_prompt, max_tokens, temperature)
            elif provider == "openai":
                result = await self.generate_text_openai(prompt, system_prompt, max_tokens, temperature)
            elif provider == "deepseek":
                result = await self.generate_text_deepseek(prompt, system_prompt, max_tokens, temperature)
            elif provider == "yandexgpt":
                result = await self.generate_text_yandexgpt(prompt, system_prompt, max_tokens, temperature)
            elif provider == "gigachat":
                result = await self.generate_text_gigachat(prompt, system_prompt, max_tokens, temperature)
            else:
                provider = "yandexgpt"
                result = await self.generate_text_yandexgpt(prompt, system_prompt, max_tokens, temperature)
            
            return {
                "success": True,
                "generated_text": result.get("text", ""),
                "provider": provider,
                "model": result.get("model"),
                "tokens_used": result.get("tokens"),
                "prompt_tokens": result.get("prompt_tokens"),
                "completion_tokens": result.get("completion_tokens"),
                "reasoning_tokens": result.get("reasoning_tokens"),
                "finish_reason": result.get("finish_reason"),
                "alternative_status": result.get("alternative_status"),
                "truncated": result.get("truncated"),
            }
            
        except Exception as e:
            logger.error(f"AI generation failed: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "provider": provider
            }

# Создаем экземпляр сервиса
ai_service = AIService()
