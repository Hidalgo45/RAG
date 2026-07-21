$ErrorActionPreference = "Stop"
py -3.12 -m venv .venv
& .\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
if (-not (Test-Path ".env")) { Copy-Item ".env.example" ".env" }
ollama pull qwen2.5:3b
ollama pull nomic-embed-text
python -m src.cli check
