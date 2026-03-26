(The file `c:\Users\Slava\Desktop\project1\README.md` exists, but is empty)
# AI Backend API

Simple FastAPI backend for multiple AI providers (HuggingFace, OpenAI-compatible, DeepSeek, GigaChat).

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
