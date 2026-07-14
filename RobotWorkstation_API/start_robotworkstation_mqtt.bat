@echo off
setlocal

REM ==========================================
REM Robot Workstation MQTT Publisher
REM Laptop 1 (Enterprise/API Laptop)
REM Mosquitto is already running as a Windows Service
REM ==========================================

REM Move to this folder
cd /d %~dp0

echo.
echo ==========================================
echo Starting Robot Workstation MQTT Publisher...
echo ==========================================
echo.

start "RobotWorkstation MQTT Publisher" cmd /k ^
"C:\Users\PatelPranayPravin\urenv\Scripts\python.exe robotworkstation_mqtt_publisher.py"

timeout /t 2 >nul

echo.
echo ==========================================
echo Starting MQTT Response Subscriber...
echo ==========================================
echo.

start "MQTT Subscriber" cmd /k ^
"mosquitto_sub -h localhost -t robotworkstation/response -v"

echo.
echo ==========================================
echo SYSTEM READY
echo ==========================================
echo Broker           : localhost:1883
echo Publisher        : robotworkstation_mqtt_publisher.py
echo Request Topic    : robotworkstation/request
echo Response Topic   : robotworkstation/response
echo ==========================================
echo.

pause