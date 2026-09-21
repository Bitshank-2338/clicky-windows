@echo off
cd /d "%~dp0"
:loop
start /wait "" pythonw main.py
if %errorlevel%==0 exit /b
if %errorlevel%==3 exit /b
timeout /t 5 /nobreak >nul
goto loop
