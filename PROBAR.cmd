@echo off
cd /d "%~dp0"
python -m unittest pruebas pruebas_tiradas -v
pause
