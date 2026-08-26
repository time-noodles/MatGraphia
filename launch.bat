@echo off
chcp 65001 > NUL
title MatGraphia 物質科学データ管理システム (Windows版)
echo =================================================================
echo  🧬 MatGraphia (Windows版) ワンクリック起動中...
echo =================================================================

cd /d "%~dp0"

set "PYTHON_CMD=python"

:: Anaconda / Miniconda 環境の自動探査 ＆ py312 環境のアクティベート
if exist "%USERPROFILE%\miniconda3\Scripts\activate.bat" (
    call "%USERPROFILE%\miniconda3\Scripts\activate.bat" py312 2>NUL
) else if exist "%USERPROFILE%\anaconda3\Scripts\activate.bat" (
    call "%USERPROFILE%\anaconda3\Scripts\activate.bat" py312 2>NUL
) else if exist "C:\ProgramData\miniconda3\Scripts\activate.bat" (
    call "C:\ProgramData\miniconda3\Scripts\activate.bat" py312 2>NUL
)

echo MatGraphia Web アプリケーションを起動しています...
python -m streamlit run app.py --server.headless=false --server.port=8501

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [エラー] アプリケーションの起動に失敗しました。
    echo Python環境または Streamlit がインストールされているかご確認ください。
    pause
)
