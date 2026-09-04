@echo off
REM ============================================================
REM  Samvaadhika — Start the application
REM  Double-click this file to launch the translation platform.
REM  Run setup.bat FIRST if you haven't already.
REM ============================================================

echo.
echo  Starting Samvaadhika...
echo  Open your browser at:  http://localhost:8000
echo  Press Ctrl+C to stop.
echo.

REM Start FastAPI with the project virtual environment explicitly.
REM Avoid relying on shell activation, which can select system Python.
if not exist "venv\Scripts\python.exe" (
    echo [ERROR] Virtual environment not found. Run setup.bat first.
    pause
    exit /b 1
)

REM Start FastAPI with Uvicorn
venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

pause
