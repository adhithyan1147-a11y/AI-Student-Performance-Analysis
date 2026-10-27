@echo off
setlocal
cd /d "%~dp0"
echo ============================================
echo Student Performance Analysis - Setup
echo ============================================
where py >nul 2>nul
if errorlevel 1 (
  echo Python was not found. Install Python 3.11 or newer from python.org.
  echo During installation, select "Add Python to PATH".
  pause
  exit /b 1
)
if not exist ".venv\Scripts\python.exe" (
  py -m venv .venv
  if errorlevel 1 goto failed
)
call ".venv\Scripts\activate.bat"
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
if errorlevel 1 goto failed
if not exist ".env" (
  copy ".env.example" ".env" >nul
  echo Created .env configuration file.
)
echo.
echo Create a secure administrator password now.
python make_admin_hash.py
if errorlevel 1 goto failed
echo.
echo Open .env in Notepad and paste the password hash after ADMIN_PASSWORD_HASH=
echo Also replace FLASK_SECRET_KEY with a long random value.
notepad .env
echo.
echo Setup packages are installed.
echo When .env is saved, run run_windows.bat to start the website.
pause
exit /b 0
:failed
echo Setup failed. Check the messages above and try again.
pause
exit /b 1
