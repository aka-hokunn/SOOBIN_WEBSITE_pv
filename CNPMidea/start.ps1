# ============================================================
# Khoi dong He Thong Soobin Swimwear (PowerShell)
# ============================================================

$ErrorActionPreference = "Stop"

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  KHOI DONG SOOBIN SWIMWEAR E-COMMERCE (MVC PYTHON)" -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor Cyan

# Kiem tra Python virtual environment
$pythonPath = "backend\.venv-runtime\Scripts\python.exe"
if (-not (Test-Path $pythonPath)) {
    Write-Host "[*] Dang tao moi truong ao Python..." -ForegroundColor Yellow
    python -m venv backend\.venv-runtime
    Write-Host "[*] Dang cai dat thu vien tu requirements.txt..." -ForegroundColor Yellow
    & "backend\.venv-runtime\Scripts\pip.exe" install -r requirements.txt
}

# Chay ung dung
Write-Host "[*] Website Soobin: http://localhost:8000" -ForegroundColor Green
Write-Host "[*] Website GHTK rieng: http://localhost:8001" -ForegroundColor Green
& $pythonPath run.py
