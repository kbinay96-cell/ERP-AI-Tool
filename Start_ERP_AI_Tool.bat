@echo off
cd /d "%~dp0"
echo Starting ERP AI Tool...
echo.

REM venv activate karo
if exist ".venv-openhands\Scripts\activate.bat" (
    call ".venv-openhands\Scripts\activate.bat"
) else (
    echo WARNING: .venv-openhands not found. Using system Python.
)

python main.py

if errorlevel 1 (
    echo.
    echo ============================================================
    echo Tool band ho gaya kisi error ki wajah se. Upar dekhein.
    echo ============================================================
    pause
)