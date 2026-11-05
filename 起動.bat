@echo off
cd /d "%~dp0"
python app.py
if errorlevel 1 (
  echo.
  echo Failed to start. Run: python -m pip install -r requirements.txt
  pause
)
