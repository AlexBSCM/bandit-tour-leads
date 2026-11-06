@echo off
chcp 65001 >nul
rem Launch bot from the folder where this script lives (works on any drive/PC)
cd /d "%~dp0"

if not exist logs mkdir logs

rem --- check if bot is already running (it locks session DB) ---
powershell -NoProfile -Command "$p = Get-CimInstance Win32_Process | Where-Object { $_.Name -like 'python*' -and $_.CommandLine -like '*bot.py*' }; if ($p) { exit 1 } else { exit 0 }"
if errorlevel 1 goto restart

:launch
where python >nul 2>nul
if errorlevel 1 goto python_missing

echo [%date% %time%] Starting bot >> logs\startup.log
start "" /min pythonw.exe bot.py

ping -n 6 127.0.0.1 >nul
tasklist /FI "IMAGENAME eq pythonw.exe" 2>nul | find /I "pythonw.exe" >nul
if errorlevel 1 goto start_failed

echo [%date% %time%] Bot started OK (pythonw) >> logs\startup.log
goto :eof

:restart
echo [%date% %time%] Bot already running - restarting >> logs\startup.log
echo Bot already running, restarting...

rem --- stop old bot.py process(es) ---
powershell -NoProfile -Command "Get-CimInstance Win32_Process | Where-Object { $_.Name -like 'python*' -and $_.CommandLine -like '*bot.py*' } | ForEach-Object { Write-Host ('Stopping PID ' + $_.ProcessId); Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }"

rem --- wait for the process to die and release the session DB ---
ping -n 4 127.0.0.1 >nul

rem --- clean SQLite journal files (database is locked) ---
del /q "*.session-journal" 2>nul

rem --- wait a bit more if a process is still alive ---
powershell -NoProfile -Command "$p = Get-CimInstance Win32_Process | Where-Object { $_.Name -like 'python*' -and $_.CommandLine -like '*bot.py*' }; if ($p) { Start-Sleep -Seconds 3; $p | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }; Start-Sleep -Seconds 2 }"

goto launch

:python_missing
echo [%date% %time%] ERROR: python not found in PATH >> logs\startup.log
echo Python not found in PATH. Install Python 3.10+ and check "Add to PATH".
pause
goto :eof

:start_failed
echo [%date% %time%] WARNING: pythonw process not found after start >> logs\startup.log
goto :eof
