' BanditTour Dashboard Server - Hidden Launcher
' Запуск из папки, где лежит сам скрипт (работает на любом ПК)
Set fso = CreateObject("Scripting.FileSystemObject")
scriptDir = fso.GetParentFolderName(WScript.ScriptFullName)
Set WshShell = CreateObject("WScript.Shell")
WshShell.CurrentDirectory = scriptDir
WshShell.Run "pythonw.exe dashboard_server.py", 0, False
