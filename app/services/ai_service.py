import httpx
import asyncio
import time
import uuid
from typing import Dict, Any, Optional
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
                    return {
                        "text": data["choices"][0]["message"]["content"],
                        "model": data["model"],
                        "tokens": data.get("usage", {}).get("total_tokens", 0)
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
                    return {
                        "text": data["choices"][0]["message"]["content"],
                        "model": data["model"],
                        "tokens": data.get("usage", {}).get("total_tokens", 0)
                    }
                else:
                    logger.error(f"DeepSeek API error: {response.status_code} - {response.text}")
                    
        except Exception as e:
            logger.error(f"DeepSeek request failed: {str(e)}")
        
        return {"text": "", "model": settings.DEEPSEEK_MODEL}

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
                                return {
                                    "text": text,
                                    "model": data.get("model", giga_model),
                                    "tokens": data.get("usage", {}).get("total_tokens", 0)
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
        prompt = request_data.get("prompt", "")
        system_prompt = request_data.get("system_prompt", "Ты - полезный AI ассистент.")
        max_tokens = request_data.get("max_tokens", 500)
        temperature = request_data.get("temperature", 0.7)
        
        try:
            if provider == "huggingface":
                result = await self.generate_text_huggingface(prompt, system_prompt, max_tokens, temperature)
            elif provider == "openai":
                result = await self.generate_text_openai(prompt, system_prompt, max_tokens, temperature)
            elif provider == "deepseek":
                result = await self.generate_text_deepseek(prompt, system_prompt, max_tokens, temperature)
            elif provider == "gigachat":
                result = await self.generate_text_gigachat(prompt, system_prompt, max_tokens, temperature)
            else:
                result = await self.generate_text_huggingface(prompt, system_prompt, max_tokens, temperature)
            
            return {
                "success": True,
                "generated_text": result.get("text", ""),
                "provider": provider,
                "model": result.get("model"),
                "tokens_used": result.get("tokens")
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
