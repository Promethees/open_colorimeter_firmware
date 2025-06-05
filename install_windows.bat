@echo off
setlocal

echo Downloading Python installer...
curl -o python-installer.exe https://www.python.org/ftp/python/3.12.3/python-3.12.3-amd64.exe

echo Installing Python silently...
python-installer.exe /quiet InstallAllUsers=1 PrependPath=1 Include_pip=1

echo Waiting for installation to finish...
timeout /t 10

echo Checking Python version...
python --version

echo Installing hidapi...
pip install hidapi

echo ✅ Python and hidapi installed successfully on Windows.

endlocal
