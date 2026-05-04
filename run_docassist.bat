@echo off
setlocal

set "ROOT_DIR=%~dp0"
set "PYTHON_EXE=%ROOT_DIR%.venv\Scripts\python.exe"
set "APP_HOST=127.0.0.1"
set "APP_PORT=8000"
set "APP_URL=http://%APP_HOST%:%APP_PORT%"

cd /d "%ROOT_DIR%"

echo.
echo Starting DocAssist Java Documentation Agent
echo Project: %ROOT_DIR%
echo.

if not exist "%PYTHON_EXE%" (
    echo ERROR: Python virtual environment was not found.
    echo.
    echo Create it and install dependencies with:
    echo   py -m venv .venv
    echo   .\.venv\Scripts\python.exe -m pip install -r requirements.txt
    echo.
    pause
    exit /b 1
)

"%PYTHON_EXE%" -c "import uvicorn, fastapi" >nul 2>&1
if errorlevel 1 (
    echo ERROR: Required Python packages are missing from .venv.
    echo.
    echo Install dependencies with:
    echo   .\.venv\Scripts\python.exe -m pip install -r requirements.txt
    echo.
    pause
    exit /b 1
)

netstat -ano | findstr /R /C:":%APP_PORT% .*LISTENING" >nul 2>&1
if not errorlevel 1 (
    echo ERROR: Port %APP_PORT% is already in use.
    echo.
    echo Stop the process using that port, or run DocAssist manually with a different port:
    echo   .\.venv\Scripts\python.exe -m uvicorn backend.app.main:app --host %APP_HOST% --port 8001
    echo.
    pause
    exit /b 1
)

echo Reminder: Ollama must be running, with the configured chat and embed models available.
echo Opening %APP_URL% ...
echo Press Ctrl+C in this window to stop DocAssist.
echo.

start "" "%APP_URL%"
"%PYTHON_EXE%" -m uvicorn backend.app.main:app --host %APP_HOST% --port %APP_PORT%

echo.
echo DocAssist stopped.
pause
