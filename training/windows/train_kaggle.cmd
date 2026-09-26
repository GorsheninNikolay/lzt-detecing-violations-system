@echo off
setlocal
cd /d "%~dp0"
".venv\Scripts\python.exe" train.py --profile kaggle %*
exit /b %errorlevel%
