@echo off
cd /d "%~dp0"
py -3 -m flask --app app run --host 127.0.0.1 --port 5000
if errorlevel 1 (
    echo.
    echo Could not start the MES web app. Install dependencies with: py -3 -m pip install -r requirements.txt
    pause
)
