@echo off
setlocal EnableDelayedExpansion

set LOGFILE=vca_error.log
set "TIMESTAMP=[%date% %time%]"

echo %TIMESTAMP% Starting VC Accountant >> "%LOGFILE%"

cd /d "%~dp0"

if not exist ".venv\Scripts\activate.bat" (
    echo %TIMESTAMP% ERROR: Virtual environment folder not found >> "%LOGFILE%"
    echo.
    echo [ERROR] Virtual environment not found.
    echo Please create it by running: python -m venv .venv
    echo.
    pause
    exit /b 1
)

call .venv\Scripts\activate.bat
if errorlevel 1 (
    echo %TIMESTAMP% ERROR: Failed to activate virtual environment >> "%LOGFILE%"
    echo.
    echo [ERROR] Failed to activate the virtual environment.
    pause
    exit /b 1
)

python main.py
set APP_EXIT_CODE=%errorlevel%

call deactivate.bat >nul 2>&1

if %APP_EXIT_CODE% neq 0 (
    echo %TIMESTAMP% Application exited with error code %APP_EXIT_CODE% >> "%LOGFILE%"
    echo.
    echo [WARNING] VC Accountant exited with error code %APP_EXIT_CODE%.
    echo Check %LOGFILE% for details.
) else (
    echo %TIMESTAMP% Application closed successfully >> "%LOGFILE%"
)

pause
endlocal
