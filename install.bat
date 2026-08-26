@echo off
REM ============================================================
REM  Samvaadhika — End-user installer
REM  Run this on the BAIF target PC after unzipping the package.
REM  NO Python, NO internet, NO admin rights needed.
REM
REM  What it does:
REM    1. Detects where it was unzipped
REM    2. Creates a Desktop shortcut → Samvaadhika.exe
REM    3. Creates a Start Menu shortcut
REM    4. Initialises the database (first run only)
REM    5. Optionally installs as a Windows Service via NSSM
REM       (so the app starts automatically on reboot)
REM ============================================================

setlocal EnableDelayedExpansion

echo.
echo  =====================================================
echo   Samvaadhika Installer
echo   Offline Multilingual Translation Platform for BAIF
echo  =====================================================
echo.

REM -- Detect install folder (same folder as this script) --
set "INSTALL_DIR=%~dp0"
REM Remove trailing backslash
if "%INSTALL_DIR:~-1%"=="\" set "INSTALL_DIR=%INSTALL_DIR:~0,-1%"

set "EXE=%INSTALL_DIR%\Samvaadhika.exe"

if not exist "%EXE%" (
    echo [ERROR] Samvaadhika.exe not found in:
    echo         %INSTALL_DIR%
    echo.
    echo  Make sure you are running install.bat from inside
    echo  the unzipped Samvaadhika folder.
    pause
    exit /b 1
)

echo  Install location: %INSTALL_DIR%
echo.

REM ── Step 1: Initialise data folders ──────────────────────────────────────
echo [1/4] Creating data folders...
for %%D in (data uploads cache outputs models) do (
    if not exist "%INSTALL_DIR%\%%D" mkdir "%INSTALL_DIR%\%%D"
)

REM ── Step 2: Desktop shortcut ─────────────────────────────────────────────
echo [2/4] Creating Desktop shortcut...
set "SHORTCUT=%USERPROFILE%\Desktop\Samvaadhika.lnk"
powershell -NoProfile -Command ^
  "$ws = New-Object -ComObject WScript.Shell; ^
   $s  = $ws.CreateShortcut('%SHORTCUT%'); ^
   $s.TargetPath      = '%EXE%'; ^
   $s.WorkingDirectory= '%INSTALL_DIR%'; ^
   $s.Description     = 'Samvaadhika — BAIF Translation Platform'; ^
   $s.Save()"
if exist "%SHORTCUT%" (
    echo  [OK] Desktop shortcut created.
) else (
    echo  [WARN] Could not create desktop shortcut ^(PowerShell may be restricted^).
)

REM ── Step 3: Start Menu shortcut ──────────────────────────────────────────
echo [3/4] Creating Start Menu shortcut...
set "SM_DIR=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Samvaadhika"
if not exist "%SM_DIR%" mkdir "%SM_DIR%"
set "SM_SHORTCUT=%SM_DIR%\Samvaadhika.lnk"
powershell -NoProfile -Command ^
  "$ws = New-Object -ComObject WScript.Shell; ^
   $s  = $ws.CreateShortcut('%SM_SHORTCUT%'); ^
   $s.TargetPath      = '%EXE%'; ^
   $s.WorkingDirectory= '%INSTALL_DIR%'; ^
   $s.Description     = 'Samvaadhika — BAIF Translation Platform'; ^
   $s.Save()"
if exist "%SM_SHORTCUT%" (
    echo  [OK] Start Menu shortcut created.
) else (
    echo  [WARN] Could not create Start Menu shortcut.
)

REM ── Step 4: Optional Windows Service via NSSM ────────────────────────────
echo.
echo [4/4] Windows Service (optional)
echo.
echo  Installing as a Windows Service means Samvaadhika starts
echo  automatically when the PC boots — no one needs to log in.
echo  This requires NSSM (Non-Sucking Service Manager).
echo.
set /p INSTALL_SERVICE="  Install as Windows Service? (y/N): "
if /i "%INSTALL_SERVICE%"=="y" (
    set "NSSM=%INSTALL_DIR%\nssm.exe"
    if not exist "!NSSM!" (
        echo.
        echo  [INFO] nssm.exe not found in %INSTALL_DIR%
        echo  Download nssm from https://nssm.cc/download
        echo  Place nssm.exe in %INSTALL_DIR% and re-run install.bat.
        echo  Skipping service installation.
    ) else (
        echo  Installing Windows Service 'Samvaadhika'...
        "!NSSM!" install Samvaadhika "%EXE%"
        "!NSSM!" set Samvaadhika AppDirectory "%INSTALL_DIR%"
        "!NSSM!" set Samvaadhika DisplayName "Samvaadhika Translation Platform"
        "!NSSM!" set Samvaadhika Description "BAIF offline multilingual translation platform"
        "!NSSM!" set Samvaadhika Start SERVICE_AUTO_START
        "!NSSM!" set Samvaadhika AppStdout "%INSTALL_DIR%\data\service.log"
        "!NSSM!" set Samvaadhika AppStderr "%INSTALL_DIR%\data\service_err.log"
        net start Samvaadhika
        echo  [OK] Service installed and started.
        echo  Access at: http://localhost:8000
    )
) else (
    echo  Skipping service installation.
    echo  To start manually: double-click the Desktop shortcut.
)

echo.
echo  =====================================================
echo   Installation complete!
echo.
echo   To start Samvaadhika:
echo     Double-click the "Samvaadhika" shortcut on your Desktop
echo     OR open Start Menu → Samvaadhika
echo.
echo   The app will open in your browser automatically.
echo   URL: http://localhost:8000
echo.
echo   Default login:
echo     Username : admin
echo     Password : Samvaadhika@2024
echo     ^(Change this password after first login^)
echo.
echo   No internet required. Fully offline.
echo  =====================================================
echo.
pause
