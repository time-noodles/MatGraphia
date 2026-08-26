@echo off
chcp 65001 >nul 2>&1

REM MatGraphia Launcher

set SCRIPT_DIR=%~dp0
pushd "%SCRIPT_DIR%"

set APP_FILE=%SCRIPT_DIR%app.py

if not exist "%APP_FILE%" (
    echo [ERROR] app.py not found
    popd
    pause
    exit /b 1
)

REM Try conda run with py312
where conda >nul 2>&1
if errorlevel 1 goto :NO_CONDA

echo [INFO] Using conda env: py-antigravity
conda run -n py-antigravity --no-capture-output python -m streamlit run "%APP_FILE%"
goto :CHECK_EXIT

:NO_CONDA
echo [INFO] conda not found. Trying system python...
python -m streamlit run "%APP_FILE%"

:CHECK_EXIT
if errorlevel 1 (
    echo [ERROR] Failed to start MatGraphia
    echo [HINT] Run install_requirements.bat first
    popd
    pause
    exit /b 1
)

popd