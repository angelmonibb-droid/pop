param(
  [int]$Port = 8000,
  [int]$Threads = 8
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path -LiteralPath ".env")) {
  throw "فایل .env وجود ندارد. ابتدا .env.example را کپی و مقادیر امن آن را تنظیم کنید."
}

python -c "from app import create_app; create_app(); print('Configuration and database are ready')"
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

python -m waitress --listen="127.0.0.1:$Port" --threads=$Threads wsgi:app

