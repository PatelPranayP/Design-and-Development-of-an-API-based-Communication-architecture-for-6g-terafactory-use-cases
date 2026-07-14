@echo off
setlocal

REM ==== CONFIG ====
set PORT=8005
set HOST=0.0.0.0
set APP=sap_material_rest_api_sqlite:app

REM ==== MOVE TO BAT FILE DIRECTORY ====
cd /d %~dp0

echo.
echo Starting REST API server...
echo.

REM ==== START SERVER ====
start "SAP REST API" cmd /k "uvicorn %APP% --host %HOST% --port %PORT%"

REM ==== WAIT FOR SERVER TO START ====
timeout /t 3 >nul

REM ==== OPEN SWAGGER UI ====
start "" http://localhost:%PORT%/docs

echo.
echo REST API running at:
echo http://localhost:%PORT%
echo.
pause
