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
python --version

echo [1/7] Creating Python virtual environment...
python -m venv venv
if errorlevel 1 (
    echo [ERROR] Failed to create virtual environment.
    pause
    exit /b 1
)

echo [2/7] Activating virtual environment...
call venv\Scripts\activate.bat

echo [3/7] Upgrading pip, wheel, setuptools (prevents source-build errors)...
python -m pip install --upgrade pip wheel setuptools --quiet
if errorlevel 1 (
    echo [ERROR] Could not upgrade pip/wheel/setuptools.
    pause
    exit /b 1
)

echo [4/7] Installing Pillow (binary wheel — avoids C compiler requirement)...
pip install "Pillow>=10.4.0" --only-binary=Pillow --quiet
if errorlevel 1 (
    echo [WARN] Binary wheel not found for Pillow — trying source build...
    pip install "Pillow>=10.4.0" --quiet
)

echo [5/7] Installing remaining Python dependencies...
pip install -r requirements.txt --quiet
if errorlevel 1 (
    echo [ERROR] Dependency installation failed. Check requirements.txt.
    pause
    exit /b 1
)

echo [6/7] Creating required directories...
for %%D in (data uploads cache outputs models) do (
    if not exist "%%D" mkdir "%%D"
)

echo [7/7] Initialising database (creates tables + default admin)...
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
