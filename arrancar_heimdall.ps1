# arrancar_heimdall.ps1
Write-Host "=== Arrancando Heimdall por Telegram ===" -ForegroundColor Cyan

Write-Host "[1/4] Activando entorno virtual..." -ForegroundColor Yellow
& .\.venv\Scripts\Activate.ps1

Write-Host "[2/4] Arrancando Ollama..." -ForegroundColor Yellow
Start-Process -FilePath "ollama" -ArgumentList "serve" -WindowStyle Hidden
Start-Sleep -Seconds 5

Write-Host "[3/4] Verificando Ollama..." -ForegroundColor Yellow
try {
    $response = Invoke-RestMethod -Uri "http://localhost:11434/api/version" -Method Get
    Write-Host "Ollama OK - version: $($response.version)" -ForegroundColor Green
} catch {
    Write-Host "ERROR: Ollama no responde en http://localhost:11434" -ForegroundColor Red
    exit 1
}

Write-Host "[4/4] Arrancando bot de Telegram..." -ForegroundColor Yellow
python -m app.telegram.conector --verbose
