@echo off
setlocal EnableDelayedExpansion

REM ================================================
REM Vantage Core Launcher - With Error Logging
REM ================================================

set LOGFILE=vantage_error.log
set "TIMESTAMP=[%date% %time%]"

echo %TIMESTAMP% Starting Vantage Core >> "%LOGFILE%"

cd /d "%~dp0"

REM --- Check if virtual environment exists ---
if not exist ".venv\Scripts\activate.bat" (
    echo %TIMESTAMP% ERROR: Virtual environment folder not found >> "%LOGFILE%"
    echo.
    echo [ERROR] Virtual environment not found!
    echo Please create it by running: python -m venv .venv
    echo.
    pause
    exit /b 1
)

REM --- Activate virtual environment ---
call .venv\Scripts\activate.bat
if errorlevel 1 (
    echo %TIMESTAMP% ERROR: Failed to activate virtual environment >> "%LOGFILE%"
    echo.
    echo [ERROR] Failed to activate the virtual environment.
    pause
    exit /b 1
)

echo %TIMESTAMP% Virtual environment activated successfully >> "%LOGFILE%"

REM --- Run the application ---
python main.py
set APP_EXIT_CODE=%errorlevel%

REM --- Deactivate virtual environment ---
call deactivate.bat >nul 2>&1

REM --- Log and report exit status ---
if %APP_EXIT_CODE% neq 0 (
    echo %TIMESTAMP% Application exited with error code %APP_EXIT_CODE% >> "%LOGFILE%"
    echo.
    echo [WARNING] Vantage Core exited with error code %APP_EXIT_CODE%.
    echo Check %LOGFILE% for details.
) else (
    echo %TIMESTAMP% Application closed successfully >> "%LOGFILE%"
)

pause
endlocal