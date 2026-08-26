@echo off
setlocal

REM Install dependencies into conda env: py312
set "SCRIPT_DIR=%~dp0"
pushd "%SCRIPT_DIR%"

set "REQ_FILE=%SCRIPT_DIR%requirements.txt"
set "REQ_CORE=%SCRIPT_DIR%requirements.core.tmp.txt"

if not exist "%REQ_FILE%" (
	echo [ERROR] requirements.txt が見つかりません: %REQ_FILE%
	popd
	exit /b 1
)

echo [INFO] Using requirements: %REQ_FILE%
echo [INFO] Upgrading pip in env py312...
conda run -n py312 --no-capture-output python -m pip install --upgrade pip
if errorlevel 1 (
	echo [ERROR] pip の更新に失敗しました。
	popd
	exit /b 1
)

REM crystal-toolkit は環境依存で失敗しやすいので、まず core を先に入れる
findstr /V /R /C:"^[ ]*crystal-toolkit" "%REQ_FILE%" > "%REQ_CORE%"

echo [INFO] Installing core requirements (without crystal-toolkit)...
conda run -n py312 --no-capture-output python -m pip install -r "%REQ_CORE%" --upgrade
if errorlevel 1 (
	echo [ERROR] core requirements のインストールに失敗しました。
	del /Q "%REQ_CORE%" >nul 2>&1
	popd
	exit /b 1
)

echo [INFO] Ensuring ASE is installed...
conda run -n py312 --no-capture-output python -m pip install "ase>=3.23.0" --upgrade
if errorlevel 1 (
	echo [ERROR] ASE のインストールに失敗しました。
	del /Q "%REQ_CORE%" >nul 2>&1
	popd
	exit /b 1
)

echo [INFO] Ensuring py3Dmol is installed...
conda run -n py312 --no-capture-output python -m pip install "py3Dmol>=2.4.2" --upgrade
if errorlevel 1 (
	echo [ERROR] py3Dmol のインストールに失敗しました。
	del /Q "%REQ_CORE%" >nul 2>&1
	popd
	exit /b 1
)

echo [INFO] Installing crystal-toolkit (optional)...
conda run -n py312 --no-capture-output python -m pip install "crystal-toolkit>=2024.1.0" --upgrade
if errorlevel 1 (
	echo [WARN] crystal-toolkit のインストールに失敗しました。ASE/pymatgen は利用可能です。
)

echo [INFO] Checking key packages...
conda run -n py312 --no-capture-output python -m pip show ase pymatgen crystal-toolkit

del /Q "%REQ_CORE%" >nul 2>&1
popd
endlocal
