@echo off
setlocal ENABLEDELAYEDEXPANSION

REM =========================================
REM   AR/VR MQTT - Server + SUB + MENU PUB
REM   (SQLite version)
REM =========================================

REM ===== EDIT THESE IF NEEDED =====
set WORKDIR=C:\Users\PatelPranayPravin\ARVR_API
set MQTT_BROKER=localhost
set REQUEST_TOPIC=ar/workstation/request
set RESPONSE_TOPIC=ar/workstation/response
set PY_SERVER=ar_mqtt_api_sqlite.py

REM ===== GO TO PROJECT FOLDER =====
cd /d "%WORKDIR%"

echo.
echo ==========================================
echo   MQTT START (SQLite)
echo   Folder: %WORKDIR%
echo ==========================================
echo.

REM ===== QUICK FILE CHECK =====
if not exist "%PY_SERVER%" (
  echo [ERROR] Missing: %PY_SERVER%
  pause
  exit /b 1
)

if not exist "ar_workstations.db" (
  echo [ERROR] Missing: ar_workstations.db
  echo Put ar_workstations.db in %WORKDIR%
  pause
  exit /b 1
)

REM ===== START MOSQUITTO BROKER =====
echo Starting MQTT Broker...
start "Mosquitto Broker" cmd /k ""C:\Program Files\mosquitto\mosquitto.exe" -c "C:\Users\PatelPranayPravin\ARVR_API\mosquitto_network.conf" -v"

REM ===== WAIT FOR BROKER =====
timeout /t 3 >nul

REM ===== START MQTT API SERVER =====
echo Starting AR/VR MQTT API server...
start "Terminal 1 - MQTT API" cmd /k "cd /d "%WORKDIR%" && python %PY_SERVER%"

REM small delay so the API connects first
timeout /t 2 > nul

REM ===== START SUBSCRIBER =====
echo Starting subscriber on %RESPONSE_TOPIC% ...
start "Terminal 2 - Subscriber" cmd /k "mosquitto_sub -h %MQTT_BROKER% -t "%RESPONSE_TOPIC%""

REM small delay so subscriber is ready
timeout /t 1 > nul

REM ===== MENU LOOP =====
:menu
echo.
echo ===============================
echo   AR/VR MQTT PUBLISH MENU
echo ===============================
echo 1) Request ALL workstations
echo 2) Request ONE workstation by workstation_id
echo 3) Request with limit/offset (not supported by default)
echo 4) Exit
echo.
set /p CHOICE=Choose option (1-4): 

if "%CHOICE%"=="1" goto all
if "%CHOICE%"=="2" goto one
if "%CHOICE%"=="3" goto page
if "%CHOICE%"=="4" goto end

echo Invalid choice.
goto menu

:all
set PAYLOAD={""all"": true}
echo Publishing: %PAYLOAD%
mosquitto_pub -h %MQTT_BROKER% -t "%REQUEST_TOPIC%" -m "%PAYLOAD%"
goto menu

:one
echo.
set /p WSID=Enter workstation_id (example: WS_AR_001): 
if "%WSID%"=="" (
  echo workstation_id cannot be empty.
  goto menu
)
set PAYLOAD={""workstation_id"": ""%WSID%""}
echo Publishing: %PAYLOAD%
mosquitto_pub -h %MQTT_BROKER% -t "%REQUEST_TOPIC%" -m "%PAYLOAD%"
goto menu

:page
echo.
echo NOTE: The SQLite MQTT server file does NOT support limit/offset by default.
echo It will still send all workstations if you publish ""all"": true.
set /p LIMIT=Enter limit (e.g., 20): 
if "%LIMIT%"=="" set LIMIT=20
set /p OFFSET=Enter offset (e.g., 0): 
if "%OFFSET%"=="" set OFFSET=0
set PAYLOAD={""all"": true, ""limit"": %LIMIT%, ""offset"": %OFFSET%}
echo Publishing: %PAYLOAD%
mosquitto_pub -h %MQTT_BROKER% -t "%REQUEST_TOPIC%" -m "%PAYLOAD%"
goto menu

:end
echo.
echo Exiting menu. (The opened windows will stay open. Close them when finished.)
pause
