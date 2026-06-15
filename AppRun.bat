@echo off
:: Change directory to where your project is stored
cd /d "D:\TradePlus_Automation"

:: Activate your Python Virtual Environment
call venv\Scripts\activate

:: Execute your main python script
python app.py

:: Keep the log window open at the end
echo.
echo Automation pipeline run finished.
pause