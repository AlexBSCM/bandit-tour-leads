# Настройка автозапуска BanditTour при входе в Windows (Планировщик заданий).
# Создаёт задачи:
#   - "BanditTour Bot Autostart" : запуск бота при входе (через 1 мин)
#   - "BanditTour Watchdog"      : проверка/перезапуск бота каждые 5 минут
# Запуск: powershell -ExecutionPolicy Bypass -File install_autostart.ps1 (от администратора)

$ProjectDir = $PSScriptRoot
$ErrorActionPreference = "Stop"

$user = "$env:USERDOMAIN\$env:USERNAME"
if (-not $env:USERDOMAIN) { $user = $env:USERNAME }

$sched = New-Object -ComObject Schedule.Service
$sched.Connect()
$folder = $sched.GetFolder("\")

function Remove-Task {
    param([string]$Name)
    try { $folder.DeleteTask($Name, 0) } catch { }
    try { Unregister-ScheduledTask -TaskName $Name -Confirm:$false -ErrorAction SilentlyContinue } catch { }
}

function New-BaseTask {
    $task = $sched.NewTask(0)
    $task.Principal.UserId = $user
    $task.Principal.LogonType = 3 # TASK_LOGON_INTERACTIVE_TOKEN
    $task.Principal.RunLevel = 0  # TASK_RUNLEVEL_LUA
    $task.Settings.AllowHardTerminate = $true
    $task.Settings.StartWhenAvailable = $true
    $task.Settings.RunOnlyIfNetworkAvailable = $false
    $task.Settings.DisallowStartIfOnBatteries = $false
    $task.Settings.StopIfGoingOnBatteries = $false
    $task.Settings.ExecutionTimeLimit = "PT0S"
    $task.Settings.MultipleInstances = 2 # TASK_INSTANCES_IGNORE_NEW
    return $task
}

function Add-ExecAction {
    param($task, [string]$Exe, [string]$Arguments)
    $action = $task.Actions.Create(0)
    $action.Path = $Exe
    $action.Arguments = $Arguments
    $action.WorkingDirectory = $ProjectDir
    return $action
}

# Удаляем старые задачи (наши предыдущие имена тоже)
foreach ($n in @("BanditTour Autostart","BanditTour Bot Autostart","BanditTour Dashboard Autostart","BanditTour Watchdog")) {
    Remove-Task $n
}

# ===================== Bot Autostart =====================
$taskA = New-BaseTask
Add-ExecAction $taskA "wscript.exe" ('"' + (Join-Path $ProjectDir "run_bot_hidden.vbs") + '"') | Out-Null

$trigA = $taskA.Triggers.Create(9) # TASK_TRIGGER_LOGON
$trigA.Delay = "PT1M"

$folder.RegisterTaskDefinition("BanditTour Bot Autostart", $taskA, 6, $user, $null, 3) | Out-Null
Write-Host "OK: задача 'BanditTour Bot Autostart' создана."

# ===================== Dashboard Autostart =====================
$taskD = New-BaseTask
Add-ExecAction $taskD "wscript.exe" ('"' + (Join-Path $ProjectDir "run_dashboard_hidden.vbs") + '"') | Out-Null

$trigD = $taskD.Triggers.Create(9) # TASK_TRIGGER_LOGON
$trigD.Delay = "PT1M"

$folder.RegisterTaskDefinition("BanditTour Dashboard Autostart", $taskD, 6, $user, $null, 3) | Out-Null
Write-Host "OK: задача 'BanditTour Dashboard Autostart' создана."

# ===================== Watchdog =====================
$taskW = New-BaseTask
$taskW.Settings.ExecutionTimeLimit = "PT5M"
Add-ExecAction $taskW "wscript.exe" ('"' + (Join-Path $ProjectDir "run_watchdog_hidden.vbs") + '"') | Out-Null

$trigW = $taskW.Triggers.Create(9) # TASK_TRIGGER_LOGON
$trigW.Delay = "PT1M"
$rep = $trigW.Repetition
$rep.Interval = "PT5M"
$rep.Duration = "P3650D"

$folder.RegisterTaskDefinition("BanditTour Watchdog", $taskW, 6, $user, $null, 3) | Out-Null
Write-Host "OK: задача 'BanditTour Watchdog' создана."

Write-Host ""
Write-Host "Проверка:"
Get-ScheduledTask -TaskName "BanditTour Bot Autostart","BanditTour Dashboard Autostart","BanditTour Watchdog" | Select-Object TaskName, State | Format-Table -AutoSize
