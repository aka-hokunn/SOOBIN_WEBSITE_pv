@echo off
chcp 65001 > nul
echo ============================================================
echo   KHOI DONG HE THONG SOOBIN SWIMWEAR E-COMMERCE (MVC PYTHON)
echo ============================================================

REM Kiem tra moi truong ao Python
if not exist "backend\.venv-runtime\Scripts\python.exe" (
    echo [*] Dang khoi tao moi truong ao Python (.venv)...
    python -m venv backend\.venv-runtime
    echo [*] Dang cai dat cac thu vien can thiet tu requirements.txt...
    backend\.venv-runtime\Scripts\pip.exe install -r requirements.txt
)

REM Khoi dong server
echo [*] Website Soobin: http://localhost:8000
echo [*] Website GHTK rieng: http://localhost:8001
backend\.venv-runtime\Scripts\python.exe run.py
pause
