# BanditTour Bot Watchdog
# Проверяет, что запущен именно bot.py, и перезапускает его при необходимости.
# Запуск вручную:  powershell -ExecutionPolicy Bypass -File watchdog.ps1
# Для автозапуска: Планировщик заданий Windows каждые 5 минут.

$ProjectDir = $PSScriptRoot
$BotScript = Join-Path $ProjectDir "bot.py"
$BatPath = Join-Path $ProjectDir "run_bot.bat"
$LogFile = Join-Path $ProjectDir "logs\watchdog.log"
$MaxLogSize = 1MB

function Write-Log {
    param([string]$Message)
    $logDir = Split-Path $LogFile -Parent
    if (-not (Test-Path $logDir)) { New-Item -ItemType Directory -Path $logDir -Force | Out-Null }
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $line = "[$timestamp] $Message"
    Add-Content -Path $LogFile -Value $line -Encoding UTF8
    $item = Get-Item $LogFile -ErrorAction SilentlyContinue
    if ($item -and $item.Length -gt $MaxLogSize) {
        Remove-Item $LogFile -Force
        Add-Content -Path $LogFile -Value $line -Encoding UTF8
    }
}

function Send-TelegramAlert {
    param([string]$Message)
    try {
        $configPath = Join-Path $ProjectDir "test_config.json"
        if (-not (Test-Path $configPath)) { return }
        $config = Get-Content $configPath -Raw -Encoding UTF8 | ConvertFrom-Json
        $url = "https://api.telegram.org/bot$($config.bot_token)/sendMessage"
        $body = @{ chat_id = $config.notify_chat_id; text = $Message } | ConvertTo-Json
        Invoke-RestMethod -Uri $url -Method Post -Body $body -ContentType "application/json; charset=utf-8" | Out-Null
    } catch {
        Write-Log "Не удалось отправить Telegram-уведомление: $_"
    }
}

function Get-BotProcess {
    # Ищем именно процесс, в командной строке которого есть bot.py,
    # а не любой python в системе.
    try {
        return Get-CimInstance Win32_Process -ErrorAction Stop |
            Where-Object { ($_.Name -eq "python.exe" -or $_.Name -eq "pythonw.exe") -and $_.CommandLine -like "*bot.py*" }
    } catch {
        Write-Log "Не удалось опросить процессы: $_"
        return $null
    }
}

$botProcess = Get-BotProcess

if ($botProcess) {
    Write-Log "OK: bot running (PID $($botProcess.ProcessId))"
    exit 0
}

Write-Log "WARNING: bot.py not running, restarting..."

# Чистим journal-файлы SQLite (ошибка database is locked)
Get-ChildItem $ProjectDir -Filter "*.session-journal" -ErrorAction SilentlyContinue | Remove-Item -Force -ErrorAction SilentlyContinue

if (Test-Path $BatPath) {
    Start-Process -FilePath $BatPath -WorkingDirectory $ProjectDir
    Write-Log "OK: restart initiated via run_bot.bat"
    Start-Sleep -Seconds 20
    $botProcess = Get-BotProcess
    if ($botProcess) {
        Write-Log "OK: bot successfully restarted (PID $($botProcess.ProcessId))"
        Send-TelegramAlert -Message "BanditTour Bot был остановлен и автоматически перезапущен (watchdog). Время: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
    } else {
        Write-Log "ERROR: bot failed to start after restart attempt"
        Send-TelegramAlert -Message "BanditTour Bot НЕ удалось перезапустить! Время: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss'). Проверьте вручную."
    }
} else {
    Write-Log "ERROR: run_bot.bat not found at $BatPath"
}
