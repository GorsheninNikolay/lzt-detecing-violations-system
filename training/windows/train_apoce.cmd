@echo off
setlocal
cd /d "%~dp0"
".venv\Scripts\python.exe" train.py --profile apoce %*
exit /b %errorlevel%
