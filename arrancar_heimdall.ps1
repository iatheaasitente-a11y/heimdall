# arrancar_heimdall.ps1
Write-Host "=== Arrancando Heimdall por Telegram ===" -ForegroundColor Cyan

Write-Host "[1/4] Activando entorno virtual..." -ForegroundColor Yellow
& .\.venv\Scripts\Activate.ps1

Write-Host "[2/4] Verificando Ollama..." -ForegroundColor Yellow
$ollamaUrl = "http://127.0.0.1:11434/api/version"

try {
    $response = Invoke-RestMethod -Uri $ollamaUrl -Method Get -TimeoutSec 5
    Write-Host "Ollama OK - version: $($response.version)" -ForegroundColor Green
} catch {
    Write-Host "Ollama no responde. Iniciando servidor..." -ForegroundColor Yellow
    Start-Process -FilePath "ollama" -ArgumentList "serve" -WindowStyle Hidden
    Start-Sleep -Seconds 5

    try {
        $response = Invoke-RestMethod -Uri $ollamaUrl -Method Get -TimeoutSec 5
        Write-Host "Ollama OK - version: $($response.version)" -ForegroundColor Green
    } catch {
        Write-Host "ERROR: Ollama no responde en http://127.0.0.1:11434" -ForegroundColor Red
        exit 1
    }
}

Write-Host "[3/4] Precargando modelo de texto..." -ForegroundColor Yellow
try {
    $null = Invoke-RestMethod -Uri "http://127.0.0.1:11434/api/generate" -Method Post -ContentType "application/json" -Body '{"model":"qwen3:4b","prompt":"OK","stream":false,"keep_alive":"30m"}' -TimeoutSec 120
    Write-Host "Modelo qwen3:4b listo." -ForegroundColor Green
} catch {
    Write-Host "AVISO: no se pudo precargar qwen3:4b." -ForegroundColor Yellow
}

Write-Host "[4/4] Arrancando bot de Telegram..." -ForegroundColor Yellow
$env:HEIMDALL_LLM_TIMEOUT = "120"
python .\arrancar_telegram.py