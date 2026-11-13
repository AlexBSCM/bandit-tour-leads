# Удаление автозапуска BanditTour.
# Запуск: powershell -ExecutionPolicy Bypass -File uninstall_autostart.ps1

$ErrorActionPreference = "SilentlyContinue"
foreach ($name in @("BanditTour Bot Autostart","BanditTour Dashboard Autostart","BanditTour Watchdog")) {
    Unregister-ScheduledTask -TaskName $name -Confirm:$false
    Write-Host "Удалена задача: $name"
}
Write-Host "Готово."
