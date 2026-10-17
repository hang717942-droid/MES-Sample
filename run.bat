@echo off
cd /d "%~dp0"
py -3 "%~dp0app.py"
if errorlevel 1 (
    echo.
    echo Could not start the MES web app. Install dependencies with: py -3 -m pip install -r requirements.txt
    pause
)
