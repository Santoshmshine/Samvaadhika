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
if not exist "dist\Samvaadhika\data"    mkdir "dist\Samvaadhika\data"
if not exist "dist\Samvaadhika\uploads" mkdir "dist\Samvaadhika\uploads"
if not exist "dist\Samvaadhika\cache"   mkdir "dist\Samvaadhika\cache"
if not exist "dist\Samvaadhika\outputs" mkdir "dist\Samvaadhika\outputs"

REM -- Copy project-provided models, ffmpeg and fonts into the distribution
if exist "models" (
    echo Copying models/ to dist\Samvaadhika\models\ ...
    xcopy "models" "dist\Samvaadhika\models" /E /I /Y >nul
) else (
    echo No local models/ folder to copy.
)

if exist "ffmpeg" (
    echo Copying ffmpeg/ to dist\Samvaadhika\ffmpeg\ ...
    xcopy "ffmpeg" "dist\Samvaadhika\ffmpeg" /E /I /Y >nul
) else (
    echo No local ffmpeg/ folder to copy.
)

if exist "fonts" (
    echo Copying fonts/ to dist\Samvaadhika\fonts\ ...
    xcopy "fonts" "dist\Samvaadhika\fonts" /E /I /Y >nul
) else (
    echo No local fonts/ folder to copy.
)

REM -- Copy the end-user installer --
copy /y install.bat "dist\Samvaadhika\install.bat" >nul

REM -- Write README_INSTALL.txt for BAIF IT --
echo Samvaadhika - Installation Instructions> "dist\Samvaadhika\README_INSTALL.txt"
echo ========================================>> "dist\Samvaadhika\README_INSTALL.txt"
echo.>> "dist\Samvaadhika\README_INSTALL.txt"
echo 1. Copy this entire folder to the target PC>> "dist\Samvaadhika\README_INSTALL.txt"
echo    Recommended: C:\Samvaadhika\>> "dist\Samvaadhika\README_INSTALL.txt"
echo.>> "dist\Samvaadhika\README_INSTALL.txt"
echo 2. Double-click install.bat>> "dist\Samvaadhika\README_INSTALL.txt"
echo    Creates Desktop and Start Menu shortcuts.>> "dist\Samvaadhika\README_INSTALL.txt"
echo.>> "dist\Samvaadhika\README_INSTALL.txt"
echo 3. Double-click the Samvaadhika Desktop shortcut.>> "dist\Samvaadhika\README_INSTALL.txt"
echo    The app opens in your browser automatically.>> "dist\Samvaadhika\README_INSTALL.txt"
echo    URL: http://localhost:8000>> "dist\Samvaadhika\README_INSTALL.txt"
echo.>> "dist\Samvaadhika\README_INSTALL.txt"
echo Default login:>> "dist\Samvaadhika\README_INSTALL.txt"
echo   Username : admin>> "dist\Samvaadhika\README_INSTALL.txt"
echo   Password : Samvaadhika@2024>> "dist\Samvaadhika\README_INSTALL.txt"
echo   CHANGE THIS PASSWORD after first login.>> "dist\Samvaadhika\README_INSTALL.txt"
echo.>> "dist\Samvaadhika\README_INSTALL.txt"
echo AI Models - optional, for full translation quality:>> "dist\Samvaadhika\README_INSTALL.txt"
echo   Drop model folders into the models subfolder.>> "dist\Samvaadhika\README_INSTALL.txt"
echo   See README.md in the source package for details.>> "dist\Samvaadhika\README_INSTALL.txt"
echo.>> "dist\Samvaadhika\README_INSTALL.txt"
echo Bundled runtime assets included in this package:>> "dist\Samvaadhika\README_INSTALL.txt"
echo   - ffmpeg\\ : FFmpeg executables used for audio/video processing.>> "dist\Samvaadhika\README_INSTALL.txt"
echo   - models\\ : Pre-downloaded model checkpoints (optional but recommended for best quality).>> "dist\Samvaadhika\README_INSTALL.txt"
echo   - fonts\\  : Fonts required for PDF rendering / OCR and proper UI rendering.>> "dist\Samvaadhika\README_INSTALL.txt"
echo.>> "dist\Samvaadhika\README_INSTALL.txt"
echo Notes: The `models` folder may contain large files; if disk space is limited, you may remove unused model checkpoints.>> "dist\Samvaadhika\README_INSTALL.txt"
echo To update or add assets on the target PC:>> "dist\Samvaadhika\README_INSTALL.txt"
echo   - Replace the `ffmpeg` folder to update the FFmpeg binaries.>> "dist\Samvaadhika\README_INSTALL.txt"
echo   - Place model folders under `models\` (each model in its own subfolder).>> "dist\Samvaadhika\README_INSTALL.txt"
echo   - Add fonts to the `fonts\` folder if needed by OCR or document rendering.>> "dist\Samvaadhika\README_INSTALL.txt"
echo.>> "dist\Samvaadhika\README_INSTALL.txt"
echo No Python. No internet. No IT admin rights needed.>> "dist\Samvaadhika\README_INSTALL.txt"

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
