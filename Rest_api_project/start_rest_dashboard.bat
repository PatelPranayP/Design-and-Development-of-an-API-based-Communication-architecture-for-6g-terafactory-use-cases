@echo off
echo =========================================
echo REST API TEST MODE (NO ROBOT)
echo Fake WebSocket + REST Backend + Frontend
echo =========================================

REM -----------------------------------------
REM 1. Start Fake WebSocket Server (PORT 9090)
REM -----------------------------------------
echo Starting Fake WebSocket Server...
start cmd /k "cd /d C:\Users\PatelPranayPravin\Rest_api_project && python fake_ws_server.py"

timeout /t 3

REM -----------------------------------------
REM 2. Start REST API Backend (NO venv)
REM -----------------------------------------
echo Starting REST API Backend...
start cmd /k "cd /d C:\Users\PatelPranayPravin\Rest_api_project\backend && python -m uvicorn rest_to_websocket_full_api:app --host 0.0.0.0 --port 8000 --reload"

timeout /t 3

REM -----------------------------------------
REM 3. Start Frontend Dashboard
REM -----------------------------------------
echo Starting Frontend Dashboard...
start cmd /k "cd /d C:\Users\PatelPranayPravin\Rest_api_project\frontend && npm run dev -- --host"

timeout /t 5

REM -----------------------------------------
REM 4. Open Dashboard
REM -----------------------------------------
start http://localhost:5173
