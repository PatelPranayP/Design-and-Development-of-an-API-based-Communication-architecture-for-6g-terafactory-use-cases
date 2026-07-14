@echo off
setlocal EnableExtensions
title ARVR - REST API (SQLite)

set "PROJECT_DIR=C:\Users\PatelPranayPravin\ARVR_API"
cd /d "%PROJECT_DIR%"

echo.
echo ==========================================
echo   REST API START (SQLite)
echo   Folder: %PROJECT_DIR%
echo ==========================================
echo.

REM --- Show files for quick sanity check
dir /b
echo.

REM --- Check Python
python --version
if errorlevel 1 (
  echo.
  echo [ERROR] Python not found in PATH.
  echo Install Python and tick: "Add Python to PATH"
  echo.
  pause
  exit /b 1
)

REM --- Required files
if not exist "ar_rest_api_sqlite.py" (
  echo [ERROR] Missing: ar_rest_api_sqlite.py
  pause
  exit /b 1
)
if not exist "ar_workstations.db" (
  echo [ERROR] Missing: ar_workstations.db
  echo Put ar_workstations.db in this folder.
  pause
  exit /b 1
)

REM --- Create venv if needed
if not exist "venv\Scripts\activate.bat" (
  echo Creating venv...
  python -m venv venv
  if errorlevel 1 (
    echo [ERROR] venv creation failed.
    pause
    exit /b 1
  )
)

REM --- Activate venv
call "venv\Scripts\activate.bat"
if errorlevel 1 (
  echo [ERROR] Could not activate venv.
  pause
  exit /b 1
)

REM --- Install deps
echo Installing dependencies...
python -m pip install --upgrade pip
python -m pip install fastapi uvicorn

echo.
echo Starting REST API at:
echo   http://localhost:8001/api/ar/workstations
echo   Swagger UI:
echo   http://localhost:8001/docs
echo.

REM --- Open Swagger UI automatically (small delay)
echo Opening Swagger UI...
timeout /t 3 /nobreak >nul
start "" http://localhost:8001/docs

REM --- Run server
python -m uvicorn ar_rest_api_sqlite:app --host 0.0.0.0 --port 8001 --reload

echo.
echo REST API stopped.
pause
endlocal
