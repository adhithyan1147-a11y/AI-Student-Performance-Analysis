@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Run setup_windows.bat first.
  pause
  exit /b 1
)
call ".venv\Scripts\activate.bat"
if not exist ".env" (
  echo Missing .env. Run setup_windows.bat first.
  pause
  exit /b 1
)
python app.py
pause
