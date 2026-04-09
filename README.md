(The file `c:\Users\Slava\Desktop\project1\README.md` exists, but is empty)
# AI Backend API

Simple FastAPI backend for multiple AI providers (HuggingFace, OpenAI-compatible, DeepSeek, YandexGPT, GigaChat).

## Installation

Create a virtual environment and install requirements:

```bash
python -m venv venv
source venv/bin/activate  # or .\venv\Scripts\Activate.ps1 on Windows
pip install -r requirements.txt
```

If you prefer to install the `gigachat` SDK separately or to get a specific version:

```bash
pip install gigachat
```

## Run

```bash
python -m uvicorn app.main:app --reload
```

See `.env` for configuration options.

## YandexGPT

To use YandexGPT, configure these variables in `.env`:

```env
YANDEX_API_KEY="your_api_key"
YANDEX_IAM_TOKEN=""
YANDEX_FOLDER_ID="your_folder_id"
YANDEX_API_BASE="https://llm.api.cloud.yandex.net/v1"
YANDEX_MODEL="yandexgpt/latest"
AI_PROVIDER="yandexgpt"
```

Notes:

- Set either `YANDEX_API_KEY` or `YANDEX_IAM_TOKEN`.
- If `YANDEX_MODEL` is not a full `gpt://...` URI, `YANDEX_FOLDER_ID` is required.
- The backend sends YandexGPT requests in one call to the official `foundationModels/v1/completion` endpoint using `messages` (`system` + `user`).
- The public `prompt` field accepted by this backend now supports up to `5000` characters.
- The public `max_tokens` field accepted by this backend now supports up to `5000` tokens.
- If `max_tokens` is omitted, the backend now defaults it to `5000`.
- YandexGPT responses now expose diagnostics such as `alternative_status`, `truncated`, `prompt_tokens`, `completion_tokens`, and `reasoning_tokens`.
