' BanditTour Bot - Hidden Launcher (для автозапуска через Планировщик заданий)
' Запускает run_bot.bat полностью скрытно, без окна консоли.
' Запуск из папки, где лежит сам скрипт (работает на любом ПК)
Set fso = CreateObject("Scripting.FileSystemObject")
scriptDir = fso.GetParentFolderName(WScript.ScriptFullName)
Set WshShell = CreateObject("WScript.Shell")
WshShell.CurrentDirectory = scriptDir
WshShell.Run "cmd /c run_bot.bat", 0, False
