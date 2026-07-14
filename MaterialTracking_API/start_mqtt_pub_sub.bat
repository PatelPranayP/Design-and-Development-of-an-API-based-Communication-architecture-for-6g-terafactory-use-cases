@echo off
setlocal ENABLEDELAYEDEXPANSION

REM ===== CONFIG =====
set DB_NAME=sap_material.db
set MQTT_BROKER=localhost
set REQUEST_TOPIC=sap/material/request
set RESPONSE_TOPIC=sap/material/response

REM ===== START MOSQUITTO BROKER =====
echo Starting MQTT Broker...
start "Mosquitto Broker" cmd /k ""C:\Program Files\mosquitto\mosquitto.exe" -c "C:\Users\PatelPranayPravin\ARVR_API\mosquitto_network.conf" -v"

REM ===== WAIT FOR BROKER =====
timeout /t 3 >nul

REM ===== CHECK DB FILE =====
cd /d %~dp0
if not exist "%DB_NAME%" (
  echo [ERROR] "%DB_NAME%" not found in this folder.
  echo Put your SQLite DB in the same folder and name it "%DB_NAME%".
  pause
  exit /b 1
)

REM ===== START MQTT API SERVER (Python) =====
echo Starting MQTT API server (SQLite)...
start "SAP MQTT API (SQLite)" cmd /k "cd /d %~dp0 && set SAP_DB_PATH=%DB_NAME% && python sap_material_mqtt_api_sqlite.py"

REM ===== START SUBSCRIBER (RESPONSE LISTENER) =====
echo Starting MQTT subscriber on %RESPONSE_TOPIC% ...
start "MQTT SUB (Response)" cmd /k "mosquitto_sub -h %MQTT_BROKER% -t ""%RESPONSE_TOPIC%"""

REM ===== Use a temp file for JSON to avoid Windows quoting issues =====
set TMPJSON=%TEMP%\sap_mqtt_request.json

REM ===== MENU LOOP =====
:menu
echo.
echo ===============================
echo   MQTT PUBLISH MENU (SQLite)
echo ===============================
echo 1) Get ALL (limit/offset)
echo 2) Filter by ONE field (Column=Value)
echo 3) Filter by TWO fields (Column1=Value1 AND Column2=Value2)
echo 4) Get by row_id
echo 5) Exit
echo.
set /p CHOICE=Choose option (1-5):

if "%CHOICE%"=="1" goto all
if "%CHOICE%"=="2" goto onefilter
if "%CHOICE%"=="3" goto twofilter
if "%CHOICE%"=="4" goto rowid
if "%CHOICE%"=="5" goto end

echo Invalid choice.
goto menu

:all
set /p LIMIT=Enter limit (e.g., 20):
if "%LIMIT%"=="" set LIMIT=20
set /p OFFSET=Enter offset (e.g., 0):
if "%OFFSET%"=="" set OFFSET=0

> "%TMPJSON%" echo {"all": true, "limit": %LIMIT%, "offset": %OFFSET%}
echo Publishing (file): "%TMPJSON%"
type "%TMPJSON%"
mosquitto_pub -h %MQTT_BROKER% -t "%REQUEST_TOPIC%" -f "%TMPJSON%"
goto menu

:onefilter
echo.
echo IMPORTANT: Column name must match DB column exactly (case/spaces).
set /p COL=Enter column name (e.g., MaterialNumber or Plant):
set /p VAL=Enter value (exact match):
set /p LIMIT=Enter limit (e.g., 20):
if "%LIMIT%"=="" set LIMIT=20
set /p OFFSET=Enter offset (e.g., 0):
if "%OFFSET%"=="" set OFFSET=0

> "%TMPJSON%" echo {"filters": {"%COL%": "%VAL%"}, "limit": %LIMIT%, "offset": %OFFSET%}
echo Publishing (file): "%TMPJSON%"
type "%TMPJSON%"
mosquitto_pub -h %MQTT_BROKER% -t "%REQUEST_TOPIC%" -f "%TMPJSON%"
goto menu

:twofilter
echo.
echo IMPORTANT: Column names must match DB columns exactly (case/spaces).
set /p COL1=Enter column1 (e.g., MaterialNumber):
set /p VAL1=Enter value1:
set /p COL2=Enter column2 (e.g., Plant):
set /p VAL2=Enter value2:
set /p LIMIT=Enter limit (e.g., 20):
if "%LIMIT%"=="" set LIMIT=20
set /p OFFSET=Enter offset (e.g., 0):
if "%OFFSET%"=="" set OFFSET=0

> "%TMPJSON%" echo {"filters": {"%COL1%": "%VAL1%", "%COL2%": "%VAL2%"}, "limit": %LIMIT%, "offset": %OFFSET%}
echo Publishing (file): "%TMPJSON%"
type "%TMPJSON%"
mosquitto_pub -h %MQTT_BROKER% -t "%REQUEST_TOPIC%" -f "%TMPJSON%"
goto menu

:rowid
set /p RID=Enter row_id (e.g., 10):
if "%RID%"=="" set RID=1

> "%TMPJSON%" echo {"row_id": %RID%}
echo Publishing (file): "%TMPJSON%"
type "%TMPJSON%"
mosquitto_pub -h %MQTT_BROKER% -t "%REQUEST_TOPIC%" -f "%TMPJSON%"
goto menu

:end
echo Exiting menu. (Windows opened by this script will stay open.)
echo You can close them when you're done.
pause
