@echo off
REM ============================================================
REM  Samvaadhika — Build standalone Windows executable
REM  Run this on the DEVELOPER machine (needs Python + internet)
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
python --version

REM -- Activate venv if present --
if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate.bat
    echo [OK] Virtual environment activated.
) else (
    echo [INFO] No venv found — using system Python.
    echo [INFO] Creating a fresh venv for the build...
    python -m venv venv
    call venv\Scripts\activate.bat
)

REM -- Upgrade pip + build tools FIRST (prevents source-build failures) --
echo [1/5] Upgrading pip, wheel, setuptools...
python -m pip install --upgrade pip wheel setuptools --quiet
if errorlevel 1 (
    echo [ERROR] Could not upgrade pip/wheel/setuptools.
    pause
    exit /b 1
)

REM -- Install Pillow from binary wheel only (avoids C compiler requirement) --
echo [2/5] Installing Pillow (binary wheel only)...
pip install "Pillow>=10.4.0" --only-binary=Pillow --quiet
if errorlevel 1 (
    echo [WARN] Pillow binary wheel not available for this Python version.
    echo        Trying without --only-binary flag...
    pip install "Pillow>=10.4.0" --quiet
)

REM -- Install all other app dependencies --
echo [3/5] Installing app dependencies...
pip install -r requirements.txt --quiet
if errorlevel 1 (
    echo [ERROR] Dependency installation failed. See output above.
    pause
    exit /b 1
)

REM -- Install / upgrade PyInstaller --
echo [4/5] Installing PyInstaller...
pip install "pyinstaller>=6.10.0" --quiet
if errorlevel 1 (
    echo [ERROR] Could not install PyInstaller.
    pause
    exit /b 1
)

REM -- Clean previous build --
echo [5/5] Cleaning previous build artefacts...
if exist "build"            rmdir /s /q build
if exist "dist\Samvaadhika" rmdir /s /q dist\Samvaadhika

REM -- Run PyInstaller --
echo.
echo  Building executable (this takes 2-5 minutes)...
echo.
pyinstaller samvaadhika.spec --noconfirm
if errorlevel 1 (
    echo.
    echo [ERROR] PyInstaller build failed. Check output above.
    echo.
    echo  Common fixes:
    echo    - Missing hidden import: add it to samvaadhika.spec hiddenimports
    echo    - Missing data file: add it to samvaadhika.spec datas
    echo    - Run:  pip install pyinstaller --upgrade
    pause
    exit /b 1
)

REM -- Copy runtime folders that must sit NEXT TO the exe --
echo.
echo  Copying runtime folders into dist\Samvaadhika\...
for %%D in (models data uploads cache outputs) do (
    if not exist "dist\Samvaadhika\%%D" mkdir "dist\Samvaadhika\%%D"
)

REM -- Copy the end-user installer --
copy /y install.bat "dist\Samvaadhika\install.bat" >nul

REM -- Write README_INSTALL.txt for BAIF IT --
(
echo Samvaadhika — Installation Instructions
echo ========================================
echo.
echo 1. Copy this entire folder to the target PC
echo    Recommended: C:\Samvaadhika\
echo.
echo 2. Double-click  install.bat
echo    Creates Desktop and Start Menu shortcuts.
echo.
echo 3. Double-click the "Samvaadhika" Desktop shortcut.
echo    The app opens in your browser automatically.
echo    URL: http://localhost:8000
echo.
echo Default login:
echo   Username : admin
echo   Password : Samvaadhika@2024
echo   CHANGE THIS PASSWORD after first login.
echo.
echo AI Models (optional, for full translation quality):
echo   Drop model folders into the "models" subfolder.
echo   See README.md in the source package for details.
echo.
echo No Python. No internet. No IT admin rights needed.
) > "dist\Samvaadhika\README_INSTALL.txt"

echo.
echo  =====================================================
echo   BUILD COMPLETE
echo.
echo   Deliverable:  dist\Samvaadhika\
echo   Executable:   dist\Samvaadhika\Samvaadhika.exe
echo.
echo   Next steps:
echo     1. Test by running dist\Samvaadhika\Samvaadhika.exe
echo     2. Zip the dist\Samvaadhika\ folder
echo     3. Send the zip to BAIF IT
echo        They only need to unzip and run install.bat
echo  =====================================================
echo.
pause
