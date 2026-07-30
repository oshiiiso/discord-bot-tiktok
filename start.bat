@echo off
cd /d "%~dp0"

call .venv\Scripts\activate.bat

:loop
echo [%date% %time%] Starting TikTok Notify Bot...

python main.py

echo.
echo [%date% %time%] Bot stopped. Restarting in 5 seconds...
timeout /t 5 /nobreak >nul

goto loop