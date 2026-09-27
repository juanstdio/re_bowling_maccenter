@echo off
cd /d "%~dp0"
python controlador.py
if errorlevel 1 pause
