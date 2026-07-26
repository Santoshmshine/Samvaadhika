@echo off
REM ============================================================
REM  Samvaadhika — One-time setup script for Windows
REM  Run this ONCE after cloning/copying the project folder.
REM  Requires: Python 3.10+ installed and on PATH
REM ============================================================

echo.
echo  =====================================================
echo   Samvaadhika Setup — BAIF Translation Platform
echo  =====================================================
echo.

REM -- Check Python --
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found. Install Python 3.10+ from https://python.org
    pause
    exit /b 1
)

echo [1/6] Creating Python virtual environment...
python -m venv venv
if errorlevel 1 (
    echo [ERROR] Failed to create virtual environment.
    pause
    exit /b 1
)

echo [2/6] Activating virtual environment...
call venv\Scripts\activate.bat

echo [3/6] Upgrading pip...
python -m pip install --upgrade pip --quiet

echo [4/6] Installing Python dependencies...
pip install -r requirements.txt
if errorlevel 1 (
    echo [ERROR] Dependency installation failed. Check requirements.txt and your internet connection.
    pause
    exit /b 1
)

echo [5/6] Creating required directories...
if not exist "data"    mkdir data
if not exist "uploads" mkdir uploads
if not exist "cache"   mkdir cache
if not exist "outputs" mkdir outputs
if not exist "models"  mkdir models

echo [6/6] Initialising database...
python -c "from app.database import init_db; init_db(); print('Database ready.')"
if errorlevel 1 (
    echo [ERROR] Database initialisation failed.
    pause
    exit /b 1
)

echo.
echo  =====================================================
echo   Setup complete!
echo.
echo   Default admin credentials:
echo     Username : admin
echo     Password : Samvaadhika@2024
echo.
echo   IMPORTANT: Change the admin password after first login.
echo.
echo   To start the app, run:  run.bat
echo   Then open:  http://localhost:8000
echo  =====================================================
echo.
pause
