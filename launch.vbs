' ==============================================================================
' MatGraphia Windows サイレント起動スクリプト (launch.vbs)
' 黒いコマンドプロンプト画面を表示させずにバックグラウンドで起動します。
' ==============================================================================
Set WshShell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
scriptDir = fso.GetParentFolderName(WScript.ScriptFullName)
batPath = Chr(34) & scriptDir & "\launch.bat" & Chr(34)
WshShell.Run batPath, 0, False
