@echo off
chcp 65001 >nul
rem Launch bot from the folder where this script lives (works on any drive/PC)
cd /d "%~dp0"

if not exist logs mkdir logs

rem --- guard: never start a second instance (it locks session DB) ---
powershell -NoProfile -Command "$p = Get-CimInstance Win32_Process | Where-Object { $_.Name -like 'python*' -and $_.CommandLine -like '*bot.py*' }; if ($p) { exit 1 } else { exit 0 }"
if errorlevel 1 goto already_running

where python >nul 2>nul
if errorlevel 1 goto python_missing

echo [%date% %time%] Starting bot >> logs\startup.log
start "" /min pythonw.exe bot.py

timeout /t 5 /nobreak >nul
tasklist /FI "IMAGENAME eq pythonw.exe" 2>nul | find /I "pythonw.exe" >nul
if errorlevel 1 goto start_failed

echo [%date% %time%] Bot started OK (pythonw) >> logs\startup.log
goto :eof

:already_running
echo [%date% %time%] Skipped - bot already running >> logs\startup.log
echo Bot is already running. Close it first if you want a restart.
timeout /t 5 >nul
goto :eof

:python_missing
echo [%date% %time%] ERROR: python not found in PATH >> logs\startup.log
echo Python not found in PATH. Install Python 3.10+ and check "Add to PATH".
pause
goto :eof

:start_failed
echo [%date% %time%] WARNING: pythonw process not found after start >> logs\startup.log
goto :eof
