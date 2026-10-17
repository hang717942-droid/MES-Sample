@echo off
cd /d "%~dp0"
py -3 "%~dp0app.py"
if errorlevel 1 (
    echo.
    echo Could not start the MES application. Check that Python 3 with tkinter is installed.
    pause
)
