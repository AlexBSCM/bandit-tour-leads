@echo off
chcp 65001 > nul
rem Запуск из папки, где лежит сам скрипт (работает на любом диске/ПК)
cd /d "%~dp0"

if not exist logs mkdir logs
echo [%date% %time%] Starting bot >> logs\startup.log

where python >nul 2>nul
if %errorlevel% neq 0 (
    echo [%date% %time%] ERROR: python not found in PATH >> logs\startup.log
    echo Python не найден в PATH. Установите Python 3.10+ и отметьте "Add to PATH".
    exit /b 1
)

rem Запуск бота скрыто через pythonw (без окна консоли)
start "" /min pythonw.exe bot.py

timeout /t 5 /nobreak > nul

tasklist /FI "IMAGENAME eq pythonw.exe" 2>nul | find /I "pythonw.exe" > nul
if %errorlevel% equ 0 (
    echo [%date% %time%] Bot started OK (pythonw) >> logs\startup.log
) else (
    tasklist /FI "IMAGENAME eq python.exe" 2>nul | find /I "python.exe" > nul
    if %errorlevel% equ 0 (
        echo [%date% %time%] Bot started OK (python) >> logs\startup.log
    ) else (
        echo [%date% %time%] WARNING: python process not found after start >> logs\startup.log
    )
)
