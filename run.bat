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

REM Activate virtual environment
if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate.bat
) else (
    echo [WARNING] Virtual environment not found. Run setup.bat first.
    echo           Trying system Python...
)

REM Start FastAPI with Uvicorn
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

pause
