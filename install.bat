@echo off
setlocal EnableExtensions
cd /d "%~dp0"

set "APP_NAME=QuizApp"
set "PYTHON_VERSION=3.12.0"
set "PYTHON_INSTALLER=python-installer.exe"
set "PYTHON_URL=https://www.python.org/ftp/python/%PYTHON_VERSION%/python-%PYTHON_VERSION%-amd64.exe"
set "VENV_PY=.venv\Scripts\python.exe"
set "PYTHON_EXE=python"
set "PYTHON_ARGS="

echo Preparing %APP_NAME% packaging environment...

where python >nul 2>nul
if errorlevel 1 (
    where py >nul 2>nul
    if errorlevel 1 (
        echo Python was not found. Downloading Python %PYTHON_VERSION%...
        if not exist "%PYTHON_INSTALLER%" (
            curl -L -o "%PYTHON_INSTALLER%" "%PYTHON_URL%"
            if errorlevel 1 goto :error
        )
        start /wait "" "%PYTHON_INSTALLER%" /quiet InstallAllUsers=1 PrependPath=1 Include_pip=1 Include_launcher=1
        if errorlevel 1 goto :error
        if exist "%ProgramFiles%\Python312\python.exe" (
            set "PYTHON_EXE=%ProgramFiles%\Python312\python.exe"
        ) else (
            set "PYTHON_EXE=py"
            set "PYTHON_ARGS=-3"
        )
    ) else (
        set "PYTHON_EXE=py"
        set "PYTHON_ARGS=-3"
    )
)

if not exist "%VENV_PY%" (
    echo Creating virtual environment...
    "%PYTHON_EXE%" %PYTHON_ARGS% -m venv .venv
    if errorlevel 1 goto :error
)

echo Installing build dependencies...
"%VENV_PY%" -m pip install --upgrade pip
if errorlevel 1 goto :error
"%VENV_PY%" -m pip install -r requirements.txt python-docx xlrd pyinstaller
if errorlevel 1 goto :error

echo Building PyInstaller executable...
"%VENV_PY%" -m PyInstaller --clean --noconfirm QuizApp.spec
if errorlevel 1 goto :error

set "ISCC_EXE="
for %%I in (ISCC.exe) do set "ISCC_EXE=%%~$PATH:I"
if not defined ISCC_EXE if exist "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" set "ISCC_EXE=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
if not defined ISCC_EXE if exist "%ProgramFiles%\Inno Setup 6\ISCC.exe" set "ISCC_EXE=%ProgramFiles%\Inno Setup 6\ISCC.exe"

if defined ISCC_EXE (
    echo Building installer with Inno Setup...
    "%ISCC_EXE%" quizapp.iss
    if errorlevel 1 goto :error
    echo Installer created in the output folder.
) else (
    echo Inno Setup compiler was not found.
    echo PyInstaller build created in dist. Open quizapp.iss with Inno Setup to create the installer.
)

echo Packaging complete.
pause
exit /b 0

:error
echo Packaging failed.
pause
exit /b 1
