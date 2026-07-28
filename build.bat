@echo off
REM ============================================================
REM  Samvaadhika — Build standalone Windows executable
REM  Run this on the DEVELOPER machine (needs Python + PyInstaller)
REM  Output: dist\Samvaadhika\Samvaadhika.exe
REM
REM  The resulting dist\Samvaadhika\ folder can be zipped and
REM  handed to BAIF — no Python needed on their machine.
REM ============================================================

echo.
echo  =====================================================
echo   Samvaadhika Build Script
echo   Produces a standalone Windows .exe (no Python needed)
echo  =====================================================
echo.

REM -- Check Python --
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found. Install Python 3.10+ to build.
    pause
    exit /b 1
)

REM -- Activate venv if present --
if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate.bat
    echo [OK] Virtual environment activated.
) else (
    echo [INFO] No venv found — using system Python.
)

REM -- Install / upgrade PyInstaller --
echo [1/4] Installing PyInstaller...
pip install pyinstaller --quiet
if errorlevel 1 (
    echo [ERROR] Could not install PyInstaller.
    pause
    exit /b 1
)

REM -- Install all app dependencies --
echo [2/4] Installing app dependencies...
pip install -r requirements.txt --quiet
if errorlevel 1 (
    echo [ERROR] Dependency installation failed.
    pause
    exit /b 1
)

REM -- Clean previous build --
echo [3/4] Cleaning previous build artefacts...
if exist "build"           rmdir /s /q build
if exist "dist\Samvaadhika" rmdir /s /q dist\Samvaadhika

REM -- Run PyInstaller --
echo [4/4] Building executable (this takes 2-5 minutes)...
pyinstaller samvaadhika.spec --noconfirm
if errorlevel 1 (
    echo.
    echo [ERROR] PyInstaller build failed. Check output above.
    pause
    exit /b 1
)

REM -- Copy runtime assets that must sit NEXT TO the exe --
echo.
echo  Copying runtime folders into dist\Samvaadhika\...
if not exist "dist\Samvaadhika\models"  mkdir "dist\Samvaadhika\models"
if not exist "dist\Samvaadhika\data"    mkdir "dist\Samvaadhika\data"
if not exist "dist\Samvaadhika\uploads" mkdir "dist\Samvaadhika\uploads"
if not exist "dist\Samvaadhika\cache"   mkdir "dist\Samvaadhika\cache"
if not exist "dist\Samvaadhika\outputs" mkdir "dist\Samvaadhika\outputs"

REM -- Copy the end-user installer script --
copy install.bat "dist\Samvaadhika\install.bat" >nul

REM -- Write a README_INSTALL.txt for BAIF IT --
(
echo Samvaadhika — Installation Instructions
echo ========================================
echo.
echo 1. Copy this entire folder to the target PC
echo    (e.g. C:\Samvaadhika\ or a shared network drive)
echo.
echo 2. Double-click  install.bat
echo    This creates desktop and Start Menu shortcuts.
echo.
echo 3. Double-click the desktop shortcut "Samvaadhika"
echo    The app opens in your browser automatically.
echo.
echo Default login:
echo   Username : admin
echo   Password : Samvaadhika@2024
echo   CHANGE THIS PASSWORD after first login.
echo.
echo No Python, no internet, no IT admin needed.
echo.
echo For AI model setup see README.md in the source folder.
) > "dist\Samvaadhika\README_INSTALL.txt"

echo.
echo  =====================================================
echo   BUILD COMPLETE
echo.
echo   Deliverable folder:  dist\Samvaadhika\
echo   Main executable:     dist\Samvaadhika\Samvaadhika.exe
echo.
echo   Zip dist\Samvaadhika\ and send to BAIF IT.
echo   They only need to unzip and run install.bat.
echo  =====================================================
echo.
pause
