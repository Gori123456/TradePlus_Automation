@echo off
:: Force the batch script to request Administrator elevation automatically
:: ───────────────────────────────────────────────────────────────────────
net session >nul 2>&1
if %errorLevel% == 0 (
    goto :run_script
) else (
    echo Requesting Administrator privileges...
    powershell -Command "Start-Process '%~f0' -Verb RunAs"
    exit /b
)

:run_script
:: Change directory to where your project is stored
cd /d "D:\TradePlus_Automation"

:: Activate your Python Virtual Environment
call venv\Scripts\activate

:: Execute your main python script
python app.py

:: Keep the log window open at the end if auto_close is false
echo.
echo Automation pipeline run finished.
pause