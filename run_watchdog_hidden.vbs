' BanditTour Bot Watchdog - Hidden Launcher (для Планировщика заданий)
' Запускает watchdog.ps1 полностью скрытно, без окна PowerShell.
' Запуск из папки, где лежит сам скрипт (работает на любом ПК)
Set fso = CreateObject("Scripting.FileSystemObject")
scriptDir = fso.GetParentFolderName(WScript.ScriptFullName)
Set WshShell = CreateObject("WScript.Shell")
WshShell.CurrentDirectory = scriptDir
WshShell.Run "powershell -NoProfile -ExecutionPolicy Bypass -File watchdog.ps1", 0, False
