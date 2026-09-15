$ErrorActionPreference = "Stop"
$env:PYTHONPATH = Join-Path $PSScriptRoot "src"
uv run --no-project --python 3.13 python -m codex_usage_widget