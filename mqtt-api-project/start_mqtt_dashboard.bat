@echo off
title MQTT Dashboard - Real Robot Test

echo =========================================
echo MQTT DASHBOARD - REAL ROBOT TEST
echo =========================================

REM ==========================================
REM 1. Start Mosquitto Broker
REM ==========================================
echo.
echo [1/4] Starting MQTT Broker...
start "Mosquitto Broker" cmd /k ""C:\Program Files\mosquitto\mosquitto.exe" -c C:\Users\PatelPranayPravin\ARVR_API\mosquitto_network.conf -v"

timeout /t 3 > nul

REM ==========================================
REM 2. Start FastAPI Backend
REM ==========================================
echo.
echo [2/4] Starting MQTT Backend...
start "MQTT Backend" cmd /k "cd /d C:\Users\PatelPranayPravin\mqtt-api-project\backend && uvicorn mqtt_backend_match_subscriber:app --host 0.0.0.0 --port 8000 --reload"

timeout /t 3 > nul

REM ==========================================
REM 3. Start React Dashboard
REM ==========================================
echo.
echo [3/4] Starting Dashboard...
start "React Dashboard" cmd /k "cd /d C:\Users\PatelPranayPravin\mqtt-api-project\frontend && npm start"

timeout /t 8 > nul

REM ==========================================
REM 4. Open Dashboard
REM ==========================================
echo.
echo [4/4] Opening Dashboard...
start http://localhost:3000

echo.
echo =========================================
echo MQTT Dashboard Started Successfully
echo =========================================
echo.
echo IMPORTANT:
echo.
echo Laptop is running:
echo   - MQTT Broker
echo   - FastAPI Backend
echo   - React Dashboard
echo.
echo Robot PC must be running:
echo   - ROS 2
echo   - rosbridge_server
echo   - mqtt_websocket_subscriber.py
echo.
pause