@echo off
chcp 65001 > NUL
title MatGraphia ショートカット作成ツール
echo =================================================================
echo  🧬 MatGraphia Windows デスクトップショートカット作成ツール
echo =================================================================

set "TARGET_DIR=%~dp0"
set "DESKTOP_DIR=%USERPROFILE%\Desktop"
set "VBS_SCRIPT=%TEMP%\CreateShortcut.vbs"

echo Set oWS = WScript.CreateObject("WScript.Shell") > "%VBS_SCRIPT%"
echo sLinkFile = "%DESKTOP_DIR%\MatGraphia.lnk" >> "%VBS_SCRIPT%"
echo Set oLink = oWS.CreateShortcut(sLinkFile) >> "%VBS_SCRIPT%"
echo oLink.TargetPath = "%TARGET_DIR%launch.bat" >> "%VBS_SCRIPT%"
echo oLink.WorkingDirectory = "%TARGET_DIR%" >> "%VBS_SCRIPT%"
echo oLink.Description = "MatGraphia 物質科学データ管理システム" >> "%VBS_SCRIPT%"
echo oLink.WindowStyle = 1 >> "%VBS_SCRIPT%"
echo oLink.Save >> "%VBS_SCRIPT%"

cscript //nologo "%VBS_SCRIPT%"
del "%VBS_SCRIPT%"

echo.
echo ✅ Windows デスクトップ上に 「MatGraphia」 ショートカットを作成しました！
echo 今後はデスクトップのアイコンをダブルクリックするだけで起動できます。
echo.
pause
