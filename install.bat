@echo off
echo Installing Quiz App dependencies...

REM Install Python
echo Installing Python 3.12.0...
curl -o python-installer.exe https://www.python.org/ftp/python/3.12.0/python-3.12.0-amd64.exe
python-installer.exe /quiet InstallAllUsers=1 PrependPath=1

REM Install FFmpeg
echo Installing FFmpeg...
curl -L -o ffmpeg-release.zip https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip
powershell -command "Expand-Archive -Path ffmpeg-release.zip -DestinationPath C:\FFmpeg -Force"

REM Find the FFmpeg bin directory (handles version-specific folder names)
for /d %%i in (C:\FFmpeg\*) do (
    if exist "%%i\bin\ffplay.exe" (
        setx PATH "%PATH%;%%i\bin" /M
        echo FFmpeg bin directory found: %%i\bin
        goto :ffmpeg_found
    )
)

:ffmpeg_found
REM Install Python packages
echo Installing Python packages...
python -m ensurepip
python -m pip install --upgrade pip
python -m pip install reportlab openpyxl xlrd pillow pygame pandas python-docx

echo Installation complete!
pause