@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (echo Lance install_windows.bat d'abord & pause & exit /b 1)
".venv\Scripts\python.exe" main.py
if errorlevel 1 pause
