@echo off
setlocal

REM Move to script directory
cd /d %~dp0

echo Starting Robot Workstation REST API...

start "RobotWorkstation REST API" cmd /k "C:\Users\PatelPranayPravin\urenv\Scripts\python.exe -m uvicorn robotworkstation_rest_ur_rtde:app --host 0.0.0.0 --port 8010"

timeout /t 3 >nul

start "" http://localhost:8010/docs

echo.
echo Swagger UI opened at:
echo http://localhost:8010/docs
pause